const { randomUUID } = require('crypto');
const bcrypt = require('bcryptjs');

const inMemoryStore = {
    users: new Map(),
    pantry: new Map(),
    isMemoryMode: false
};

function makeQuery(result) {
    const p = Promise.resolve(result);
    p.select = function() { return p; };
    p.lean = function() {
        return Promise.resolve(result ? JSON.parse(JSON.stringify(result)) : null);
    };
    p.sort = function() { return p; };
    return p;
}

class MemoryUserDoc {
    constructor(data) {
        this._id = data._id || data.userId || `USR_${randomUUID()}`;
        this.userId = data.userId || (typeof this._id === 'string' ? this._id : `USR_${randomUUID()}`);
        this.firstName = data.firstName || '';
        this.lastName = data.lastName || '';
        this.name = data.name || `${this.firstName} ${this.lastName}`.trim() || 'FoodCoach User';
        this.email = String(data.email || '').toLowerCase().trim();
        this.passwordHash = data.passwordHash || null;
        this.refreshTokenHash = data.refreshTokenHash || null;
        this.sessionVersion = Number(data.sessionVersion || 0);
        this.role = data.role || 'user';
        this.profilePicUrl = data.profilePicUrl || '';

        const defaultProfile = {
            age: null,
            gender: '',
            heightCm: null,
            weightKg: null,
            activityLevel: 'Moderate',
            dietType: 'Vegetarian',
            allergies: [],
            healthConditions: [],
            preferredCuisines: ['Pan-Indian'],
            applyAyurvedicConstraints: true,
            viruddhaStrictMode: 'FILTER',
            macroTargets: { calories: 2000, protein: 80, carbs: 250, fat: 65 }
        };
        const rawProfile = data.profile ? JSON.parse(JSON.stringify(data.profile)) : defaultProfile;
        this.profile = {
            ...defaultProfile,
            ...rawProfile,
            toObject: function() {
                const clone = { ...this };
                delete clone.toObject;
                return clone;
            }
        };

        this.progress = data.progress ? JSON.parse(JSON.stringify(data.progress)) : {
            points: 0,
            level: 1,
            currentStreak: 0,
            longestStreak: 0,
            badges: [],
            mealsLogged: 0,
            recipesCooked: 0
        };
        this.weeklyGoals = data.weeklyGoals ? JSON.parse(JSON.stringify(data.weeklyGoals)) : {};
        this.createdAt = data.createdAt ? new Date(data.createdAt) : new Date();
        this.updatedAt = new Date();
    }

    async save() {
        this.updatedAt = new Date();
        inMemoryStore.users.set(String(this._id), this);
        inMemoryStore.users.set(String(this.userId), this);
        inMemoryStore.users.set(String(this.email).toLowerCase(), this);
        return this;
    }

    toObject() {
        const copy = JSON.parse(JSON.stringify(this));
        delete copy.passwordHash;
        delete copy.refreshTokenHash;
        return copy;
    }
}

class MemoryUserModel {
    constructor(data) {
        return new MemoryUserDoc(data);
    }

    static async countDocuments() {
        const unique = new Set([...inMemoryStore.users.values()].map(u => u.userId));
        return unique.size;
    }

    static async init() {
        return Promise.resolve();
    }

    static findById(id) {
        const user = inMemoryStore.users.get(String(id));
        return makeQuery(user || null);
    }

    static findOne(filter) {
        const allUsers = [...new Set(inMemoryStore.users.values())];
        let match = null;
        if (filter.email) {
            const queryEmail = String(filter.email).toLowerCase().trim();
            match = allUsers.find(u => u.email === queryEmail);
        } else if (filter.userId) {
            match = allUsers.find(u => u.userId === filter.userId);
        } else if (filter._id) {
            match = inMemoryStore.users.get(String(filter._id));
        }
        return makeQuery(match || null);
    }
}

class MemoryPantryModel {
    static async countDocuments() {
        return inMemoryStore.pantry.size;
    }

    static async init() {
        return Promise.resolve();
    }

    static find(filter) {
        let items = [...inMemoryStore.pantry.values()];
        if (filter && filter.userId) {
            items = items.filter(i => i.userId === filter.userId);
        }
        return makeQuery(items);
    }

    static async create(data) {
        const itemId = data.itemId || `PNT_${randomUUID()}`;
        const item = {
            _id: itemId,
            itemId,
            userId: data.userId,
            ingredientId: data.ingredientId || '',
            name: String(data.name || '').trim(),
            quantity: Number(data.quantity === undefined ? 100 : data.quantity),
            unit: data.unit || 'g',
            daysUntilExpiry: Number(data.daysUntilExpiry === undefined ? 7 : data.daysUntilExpiry),
            category: data.category || 'Pantry Staples',
            ifctCode: data.ifctCode || null,
            createdAt: new Date(),
            updatedAt: new Date()
        };
        inMemoryStore.pantry.set(`${item.userId}:${item.itemId}`, item);
        return item;
    }

    static findOneAndUpdate(filter, update, options) {
        const key = `${filter.userId}:${filter.itemId}`;
        const item = inMemoryStore.pantry.get(key);
        if (!item) return makeQuery(null);
        const patch = update.$set || update;
        Object.assign(item, patch, { updatedAt: new Date() });
        inMemoryStore.pantry.set(key, item);
        return makeQuery(item);
    }

    static async deleteOne(filter) {
        const key = `${filter.userId}:${filter.itemId}`;
        const deleted = inMemoryStore.pantry.delete(key);
        return { deletedCount: deleted ? 1 : 0 };
    }

    static async bulkWrite(operations) {
        let matchedCount = 0;
        let deletedCount = 0;
        for (const op of operations) {
            if (op.deleteOne) {
                const { userId, itemId } = op.deleteOne.filter;
                if (inMemoryStore.pantry.delete(`${userId}:${itemId}`)) {
                    deletedCount++;
                }
            } else if (op.updateOne) {
                const { userId, itemId } = op.updateOne.filter;
                const item = inMemoryStore.pantry.get(`${userId}:${itemId}`);
                if (item) {
                    matchedCount++;
                    const patch = op.updateOne.update.$set || op.updateOne.update;
                    Object.assign(item, patch, { updatedAt: new Date() });
                }
            }
        }
        return { matchedCount, deletedCount };
    }
}

function seedInMemory(seedData) {
    inMemoryStore.users.clear();
    inMemoryStore.pantry.clear();
    inMemoryStore.isMemoryMode = true;

    const defaultPasswordHash = bcrypt.hashSync('Password123', 10);

    for (const rawUser of (seedData.users || [])) {
        const nameParts = (rawUser.name || 'User').split(' ');
        const userDoc = new MemoryUserDoc({
            ...rawUser,
            firstName: nameParts[0] || 'User',
            lastName: nameParts.slice(1).join(' ') || 'Account',
            passwordHash: defaultPasswordHash
        });
        userDoc.save();
    }

    for (const rawItem of (seedData.pantry_items || [])) {
        const itemId = rawItem.itemId;
        const item = {
            _id: itemId,
            ...rawItem,
            createdAt: new Date(),
            updatedAt: new Date()
        };
        inMemoryStore.pantry.set(`${item.userId}:${item.itemId}`, item);
    }

    return {
        userCount: new Set([...inMemoryStore.users.values()].map(u => u.userId)).size,
        pantryCount: inMemoryStore.pantry.size
    };
}

module.exports = {
    inMemoryStore,
    MemoryUserModel,
    MemoryPantryModel,
    seedInMemory
};
