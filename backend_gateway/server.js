require('dotenv').config({ path: require('path').resolve(__dirname, '../.env') });
const express = require('express');
const cors = require('cors');
const axios = require('axios');
const { randomUUID } = require('crypto');
const mongoose = require('mongoose');
const cookieParser = require('cookie-parser');
const { allocatePantryIngredient, deductPantryPlan, PantryStockConflict } = require('./pantry_inventory');
const User = require('./models/User');
const PantryItem = require('./models/PantryItem');
const authenticate = require('./middleware/authenticate');
const { router: authRouter, safeUser } = require('./routes/auth');

const app = express();
const PORT = process.env.PORT || 5001;
const ML_URL = process.env.ML_SERVICE_URL || 'http://127.0.0.1:8000';

app.use(cors({
    origin: process.env.CLIENT_URL || 'http://localhost:5173',
    credentials: true
}));
app.use(express.json({ limit: '15mb' }));
app.use(express.urlencoded({ extended: true, limit: '15mb' }));
app.use(cookieParser());

// In-memory persistent database initialized from seed (handles local and container paths)
let seedData;
try {
    seedData = require('../database/mongodb_seed.json');
} catch (e) {
    try {
        seedData = require('./mongodb_seed.json');
    } catch (err) {
        seedData = { users: [], pantry_items: [], gamification_events: [] };
    }
}
let gamificationEvents = JSON.parse(JSON.stringify(seedData.gamification_events || []));
const cookingSessions = new Map();

async function recordGamificationEvent(user, type, description) {
    if (!user) return null;

    const pointMap = {
        MEAL_LOGGED: 15,
        RECIPE_COOKED: 25,
        PANTRY_SCAN: 10,
        STREAK_MILESTONE: 50,
        AYURVEDA_CHECK: 5
    };
    const points = pointMap[type] || 10;
    if (!user.progress) {
        user.progress = { points: 0, level: 1, currentStreak: 1, badges: [], mealsLogged: 0, recipesCooked: 0 };
    }
    user.progress.points += points;
    user.progress.level = Math.floor(user.progress.points / 200) + 1;
    if (type === 'MEAL_LOGGED') user.progress.mealsLogged = (user.progress.mealsLogged || 0) + 1;
    if (type === 'RECIPE_COOKED') user.progress.recipesCooked = (user.progress.recipesCooked || 0) + 1;

    const event = {
        eventId: `EVT_${Date.now()}`,
        userId: user.userId,
        type,
        points,
        timestamp: new Date().toISOString(),
        description: description || `Completed ${type}`
    };
    await user.save();
    gamificationEvents.push(event);
    return { awardedPoints: points, event };
}

function ownsUserRoute(req, res) {
    if (req.params.id && req.params.id !== req.user.userId) {
        res.status(403).json({ error: 'You cannot access another user’s data.' });
        return false;
    }
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// System Health
// ─────────────────────────────────────────────────────────────────────────────
app.get('/api/health', async (req, res) => {
    let mlHealth = { status: 'offline' };
    try {
        const resp = await axios.get(`${ML_URL}/health`, { timeout: 3000 });
        mlHealth = resp.data;
    } catch (e) {
        mlHealth = { status: 'unreachable', error: e.message };
    }
    res.json({
        gateway: 'healthy',
        port: PORT,
        activeUsersCount: await User.countDocuments().catch(() => 0),
        pantryItemsCount: await PantryItem.countDocuments().catch(() => 0),
        databaseConnected: mongoose.connection.readyState === 1 || Boolean(require('./inMemoryDb').inMemoryStore.isMemoryMode),
        mlService: mlHealth
    });
});

    app.use('/api/auth', authRouter);
    app.use('/api', authenticate);

// ─────────────────────────────────────────────────────────────────────────────
// User & Profile Management
// ─────────────────────────────────────────────────────────────────────────────
app.get('/api/users', (req, res) => {
    res.json([safeUser(req.user)]);
});

app.get('/api/profile/:id', (req, res) => {
    if (!ownsUserRoute(req, res)) return;
    res.json(safeUser(req.user));
});

app.put('/api/profile/:id', async (req, res) => {
    if (!ownsUserRoute(req, res)) return;
    const profileFields = [
        'age', 'gender', 'heightCm', 'weightKg', 'activityLevel', 'dietType',
        'allergies', 'healthConditions', 'preferredCuisines',
        'applyAyurvedicConstraints', 'viruddhaStrictMode', 'macroTargets'
    ];
    const incoming = req.body.profile || {};
    const profilePatch = {};
    for (const field of profileFields) {
        if (Object.prototype.hasOwnProperty.call(incoming, field)) profilePatch[field] = incoming[field];
    }
    if (Array.isArray(profilePatch.allergies)) profilePatch.allergies = [...new Set(profilePatch.allergies.map(value => String(value).trim()).filter(Boolean))];
    if (Array.isArray(profilePatch.healthConditions)) profilePatch.healthConditions = [...new Set(profilePatch.healthConditions.map(value => String(value).trim()).filter(Boolean))];
    if (Array.isArray(profilePatch.preferredCuisines)) profilePatch.preferredCuisines = [...new Set(profilePatch.preferredCuisines.map(value => String(value).trim()).filter(Boolean))];

    if (req.body.firstName !== undefined) req.user.firstName = String(req.body.firstName).trim();
    if (req.body.lastName !== undefined) req.user.lastName = String(req.body.lastName).trim();
    if (req.user.firstName && req.user.lastName) req.user.name = `${req.user.firstName} ${req.user.lastName}`;
    req.user.profile = { ...req.user.profile.toObject(), ...profilePatch };
    try {
        await req.user.save();
        res.json({ status: 'success', user: safeUser(req.user) });
    } catch (error) {
        console.error('Profile save error:', error);
        res.status(400).json({ error: 'Profile values are invalid. Review the fields and try again.' });
    }
});

// ─────────────────────────────────────────────────────────────────────────────
// Pantry Management (CRUD)
// ─────────────────────────────────────────────────────────────────────────────
app.get('/api/pantry/:id', async (req, res) => {
    if (!ownsUserRoute(req, res)) return;
    const items = await PantryItem.find({ userId: req.user.userId }).sort({ createdAt: 1 }).lean();
    res.json({ userId: req.user.userId, count: items.length, items });
});

app.post('/api/pantry/:id', async (req, res) => {
    if (!ownsUserRoute(req, res)) return;
    const { name, quantity, unit, daysUntilExpiry, category, ingredientId, ifctCode } = req.body;
    if (!name) {
        return res.status(400).json({ error: 'Ingredient name is required' });
    }
    try {
        const newItem = await PantryItem.create({
        itemId: `PNT_${randomUUID()}`,
        userId: req.user.userId,
        ingredientId: ingredientId || `ING_${name.toUpperCase().replace(/\s+/g, '_')}`,
        name: name.trim(),
        quantity: quantity === undefined ? 100 : Number(quantity),
        unit: unit || 'g',
        daysUntilExpiry: daysUntilExpiry === undefined ? 7 : Number(daysUntilExpiry),
        category: category || 'Pantry Staples',
        ifctCode: ifctCode || null
        });
        res.status(201).json({ status: 'created', item: newItem });
    } catch (error) {
        res.status(400).json({ error: 'Pantry item values are invalid.' });
    }
});

app.put('/api/pantry/:id/:itemId', async (req, res) => {
    if (!ownsUserRoute(req, res)) return;
    const patch = {};
    for (const field of ['name', 'quantity', 'unit', 'daysUntilExpiry', 'category', 'ifctCode']) {
        if (Object.prototype.hasOwnProperty.call(req.body, field)) patch[field] = req.body[field];
    }
    try {
        const item = await PantryItem.findOneAndUpdate(
            { userId: req.user.userId, itemId: req.params.itemId },
            { $set: patch },
            { new: true, runValidators: true }
        ).lean();
        if (!item) return res.status(404).json({ error: 'Pantry item not found' });
        res.json({ status: 'updated', item });
    } catch (error) {
        res.status(400).json({ error: 'Pantry item values are invalid.' });
    }
});

app.delete('/api/pantry/:id/:itemId', async (req, res) => {
    if (!ownsUserRoute(req, res)) return;
    const result = await PantryItem.deleteOne({ userId: req.user.userId, itemId: req.params.itemId });
    if (!result.deletedCount) {
        return res.status(404).json({ error: 'Pantry item not found' });
    }
    res.json({ status: 'deleted', itemId: req.params.itemId });
});

app.post('/api/cooking/guide', async (req, res) => {
    const { recipeId, servings, language = 'en' } = req.body;
    const userId = req.user.userId;
    if (!recipeId) return res.status(400).json({ error: 'Recipe ID is required.' });
    if (!['en', 'hi', 'mr'].includes(language)) {
        return res.status(400).json({ error: 'Language must be en, hi, or mr.' });
    }

    try {
        const response = await axios.post(`${ML_URL}/cooking/guide`, {
            recipeId,
            servings,
            language
        }, { timeout: 240000 });
        const guide = response.data;
        const userPantry = await PantryItem.find({ userId }).lean();
        guide.pantryPlan = guide.ingredients.map(ingredient => allocatePantryIngredient(userPantry, userId, ingredient));
        const sessionId = randomUUID();
        const createdAt = Date.now();
        for (const [id, session] of cookingSessions) {
            if (createdAt - session.createdAt > 24 * 60 * 60 * 1000) cookingSessions.delete(id);
        }
        cookingSessions.set(sessionId, {
            sessionId,
            userId,
            recipeId: guide.recipeId,
            title: guide.title,
            servings: guide.servings,
            createdAt,
            pantryPlan: guide.pantryPlan,
            status: 'in_progress',
            result: null
        });
        res.json({ ...guide, sessionId });
    } catch (error) {
        res.status(error.response?.status || 500).json({ error: error.response?.data?.detail || error.message });
    }
});

app.post('/api/cooking/complete', async (req, res) => {
    const { sessionId, confirmed } = req.body;
    const userId = req.user.userId;
    if (!confirmed) return res.status(400).json({ error: 'Confirm that you finished cooking before updating pantry stock.' });
    const session = cookingSessions.get(sessionId);
    if (!session || session.userId !== userId) return res.status(404).json({ error: 'Cooking session not found.' });
    if (session.status === 'completed') return res.json({ ...session.result, alreadyCompleted: true });

    let deductionResult;
    try {
        const userPantry = await PantryItem.find({ userId }).lean();
        deductionResult = deductPantryPlan(userPantry, userId, session.pantryPlan);
    } catch (error) {
        if (error instanceof PantryStockConflict) return res.status(409).json({ error: error.message });
        throw error;
    }
    const currentItems = new Map((await PantryItem.find({ userId }).lean()).map(item => [item.itemId, item]));
    const updatedItems = new Map(deductionResult.pantry.map(item => [item.itemId, item]));
    const operations = deductionResult.consumed.map(consumed => {
        const updated = updatedItems.get(consumed.itemId);
        if (!updated) {
            return { deleteOne: { filter: { userId, itemId: consumed.itemId, quantity: currentItems.get(consumed.itemId)?.quantity } } };
        }
        return {
            updateOne: {
                filter: { userId, itemId: consumed.itemId, quantity: currentItems.get(consumed.itemId)?.quantity },
                update: { $set: { quantity: updated.quantity } }
            }
        };
    });
    if (operations.length) {
        const writeResult = await PantryItem.bulkWrite(operations, { ordered: true });
        if (writeResult.matchedCount + writeResult.deletedCount !== operations.length) {
            return res.status(409).json({ error: 'Pantry changed while completing the recipe. Refresh pantry and retry.' });
        }
    }
    const gamification = await recordGamificationEvent(
        req.user,
        'RECIPE_COOKED',
        `Cooked ${session.title} (${session.servings} serving${session.servings === 1 ? '' : 's'})`
    );
    session.status = 'completed';
    session.result = {
        status: 'completed',
        recipeId: session.recipeId,
        title: session.title,
        servings: session.servings,
        consumed: deductionResult.consumed,
        awardedPoints: gamification?.awardedPoints || 0
    };
    res.json(session.result);
});

// ─────────────────────────────────────────────────────────────────────────────
// Gamification & Progress Tracking
// ─────────────────────────────────────────────────────────────────────────────
app.get('/api/gamification/:id', (req, res) => {
    if (!ownsUserRoute(req, res)) return;
    const user = req.user;
    const userEvents = gamificationEvents.filter(e => e.userId === user.userId);
    res.json({
        userId: user.userId,
        progress: user.progress || { points: 0, level: 1, currentStreak: 0, badges: [] },
        weeklyGoals: user.weeklyGoals || {},
        recentEvents: userEvents.slice(-10)
    });
});

app.post('/api/gamification/event', async (req, res) => {
    const { type, description } = req.body;
    const result = await recordGamificationEvent(req.user, type, description);
    res.json({
        status: 'success',
        awardedPoints: result.awardedPoints,
        currentTotalPoints: req.user.progress.points,
        level: req.user.progress.level,
        event: result.event
    });
});

// ─────────────────────────────────────────────────────────────────────────────
// ML Forwarding Proxies
// ─────────────────────────────────────────────────────────────────────────────
app.post('/api/recommendations/:id', async (req, res) => {
    if (!ownsUserRoute(req, res)) return;
    try {
        const user = req.user;
        const userPantry = await PantryItem.find({ userId: user.userId }).lean();
        const resp = await axios.post(`${ML_URL}/recommend`, {
            userProfile: user.profile.toObject(),
            pantryItems: userPantry
        }, { timeout: 10000 });
        res.json(resp.data);
    } catch (e) {
        res.status(500).json({ error: e.response?.data?.detail || e.message });
    }
});

app.post('/api/meal-plan', async (req, res) => {
    try {
        const userProfile = req.user.profile.toObject();
        const resp = await axios.post(`${ML_URL}/kg/meal-plan-7-days`, {
            ...req.body,
            preferredCuisines: userProfile.preferredCuisines,
            userProfile
        }, { timeout: 10000 });
        res.json(resp.data);
    } catch (e) {
        res.status(500).json({ error: e.response?.data?.detail || e.message });
    }
});

app.post('/api/viruddha-check', async (req, res) => {
    try {
        const resp = await axios.post(`${ML_URL}/viruddha/check`, req.body, { timeout: 10000 });
        res.json(resp.data);
    } catch (e) {
        res.status(500).json({ error: e.response?.data?.detail || e.message });
    }
});

app.post('/api/chat', async (req, res) => {
    try {
        const userPantry = await PantryItem.find({ userId: req.user.userId }).lean();
        const userProfile = req.user.profile.toObject();
        const userContext = {
            dietType: userProfile.dietType,
            allergies: userProfile.allergies,
            healthConditions: userProfile.healthConditions,
            pantryItems: userPantry.map(item => item.name)
        };
        const resp = await axios.post(`${ML_URL}/chat`, {
            ...req.body,
            userId: req.user.userId,
            userContext,
            language: ['en', 'hi', 'mr', 'auto'].includes(req.body.language) ? req.body.language : 'auto',
        }, { timeout: 240000 });
        res.json(resp.data);
    } catch (e) {
        res.status(500).json({ error: e.response?.data?.detail || e.message });
    }
});

app.post('/api/cooking/guide', async (req, res) => {
    try {
        const resp = await axios.post(`${ML_URL}/cooking/guide`, {
            ...req.body,
            userId: req.user.userId
        }, { timeout: 240000 });
        res.json(resp.data);
    } catch (e) {
        res.status(e.response?.status || 500).json({ error: e.response?.data?.detail || e.message });
    }
});

app.post('/api/voice/transcribe', express.raw({ type: 'audio/*', limit: '25mb' }), async (req, res) => {
    try {
        const resp = await axios.post(`${ML_URL}/voice/transcribe`, req.body, {
            headers: {
                'Content-Type': req.get('content-type') || 'audio/webm',
                'X-Language': req.get('x-language') || 'auto'
            },
            timeout: 180000,
            maxBodyLength: 25 * 1024 * 1024
        });
        res.json(resp.data);
    } catch (e) {
        res.status(e.response?.status || 500).json({ error: e.response?.data?.detail || e.message });
    }
});

app.post('/api/voice/synthesize', async (req, res) => {
    try {
        const resp = await axios.post(`${ML_URL}/voice/synthesize`, req.body, {
            responseType: 'arraybuffer',
            timeout: 180000
        });
        res.type('audio/wav').send(Buffer.from(resp.data));
    } catch (e) {
        res.status(e.response?.status || 500).json({ error: e.response?.data?.detail || e.message });
    }
});

app.post('/api/vision/analyze', async (req, res) => {
    try {
        const resp = await axios.post(`${ML_URL}/vision/analyze`, req.body, { timeout: 25000 });
        res.json(resp.data);
    } catch (e) {
        res.status(500).json({ error: e.response?.data?.detail || e.message });
    }
});

app.post('/api/nutrition/calculate', async (req, res) => {
    try {
        const resp = await axios.post(`${ML_URL}/nutrition/calculate`, req.body, { timeout: 10000 });
        res.json(resp.data);
    } catch (e) {
        res.status(500).json({ error: e.response?.data?.detail || e.message });
    }
});

async function startServer() {
    const secretPlaceholders = ['change-before-deploy', 'replace-with-a-', 'foodcoach-local-'];
    const hasPlaceholderSecret = secret => secretPlaceholders.some(placeholder => secret?.includes(placeholder));
    if (process.env.NODE_ENV === 'production' && (
        !process.env.JWT_ACCESS_SECRET || !process.env.JWT_REFRESH_SECRET ||
        hasPlaceholderSecret(process.env.JWT_ACCESS_SECRET) ||
        hasPlaceholderSecret(process.env.JWT_REFRESH_SECRET)
    )) {
        throw new Error('Production JWT secrets must be set to unique, strong values.');
    }
    const mongoUri = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/foodcoach_ai';
    try {
        await mongoose.connect(mongoUri, { serverSelectionTimeoutMS: 3000 });
        console.log('MongoDB connected successfully');
        const userCount = await User.countDocuments().catch(() => 0);
        if (userCount === 0 && seedData.users) {
            const bcrypt = require('bcryptjs');
            const defaultPasswordHash = await bcrypt.hash('Password123', 10);
            for (const rawUser of (seedData.users || [])) {
                const nameParts = (rawUser.name || 'User').split(' ');
                await User.create({
                    ...rawUser,
                    firstName: nameParts[0] || 'User',
                    lastName: nameParts.slice(1).join(' ') || 'Account',
                    passwordHash: defaultPasswordHash
                });
            }
            for (const item of (seedData.pantry_items || [])) {
                await PantryItem.create(item);
            }
            console.log('Seeded demo accounts and pantry items into MongoDB.');
        }
    } catch (err) {
        console.warn(`\n⚠️  MongoDB unavailable at ${mongoUri} (${err.message}).`);
        console.log('✨ Switching to In-Memory Database Mode with pre-seeded demo data.');
        const { seedInMemory } = require('./inMemoryDb');
        const stats = seedInMemory(seedData);
        console.log(`✅ In-memory database initialized: ${stats.userCount} users, ${stats.pantryCount} pantry items.`);
        console.log('🔑 Demo Login: omkar.andhare@i2it.edu.in / Password123 (or register any new account)\n');
    }

    await User.init().catch(() => {});
    await PantryItem.init().catch(() => {});
    app.listen(PORT, () => {
        console.log(`FoodCoach AI Gateway running on port ${PORT}`);
        console.log(`Connected ML Service URL: ${ML_URL}`);
        console.log(`Frontend URL: ${process.env.CLIENT_URL || 'http://localhost:5173'}`);
    });
}

startServer().catch(error => {
    console.error('FoodCoach gateway encountered fatal error:', error.message);
    process.exit(1);
});
