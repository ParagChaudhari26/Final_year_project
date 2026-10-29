const mongoose = require('mongoose');
const { randomUUID } = require('crypto');

const macroTargetsSchema = new mongoose.Schema({
    calories: { type: Number, default: 2000, min: 500, max: 10000 },
    protein: { type: Number, default: 80, min: 10, max: 500 },
    carbs: { type: Number, default: 250, min: 10, max: 1000 },
    fat: { type: Number, default: 65, min: 10, max: 500 }
}, { _id: false });

const profileSchema = new mongoose.Schema({
    age: { type: Number, min: 13, max: 120, default: null },
    gender: { type: String, trim: true, default: '' },
    heightCm: { type: Number, min: 80, max: 250, default: null },
    weightKg: { type: Number, min: 25, max: 400, default: null },
    activityLevel: {
        type: String,
        enum: ['Sedentary', 'Light', 'Moderate', 'Active', 'Very Active'],
        default: 'Moderate'
    },
    dietType: {
        type: String,
        enum: ['Vegetarian', 'Vegan', 'Eggetarian', 'Non-Vegetarian', 'Any'],
        default: 'Vegetarian'
    },
    allergies: { type: [String], default: [] },
    healthConditions: { type: [String], default: [] },
    preferredCuisines: { type: [String], default: ['Pan-Indian'] },
    applyAyurvedicConstraints: { type: Boolean, default: true },
    viruddhaStrictMode: { type: String, enum: ['FILTER', 'WARN', 'OFF'], default: 'FILTER' },
    macroTargets: { type: macroTargetsSchema, default: () => ({}) }
}, { _id: false });

const progressSchema = new mongoose.Schema({
    points: { type: Number, default: 0 },
    level: { type: Number, default: 1 },
    currentStreak: { type: Number, default: 0 },
    longestStreak: { type: Number, default: 0 },
    badges: { type: [mongoose.Schema.Types.Mixed], default: [] },
    mealsLogged: { type: Number, default: 0 },
    recipesCooked: { type: Number, default: 0 }
}, { _id: false });

const userSchema = new mongoose.Schema({
    userId: { type: String, unique: true, default: () => `USR_${randomUUID()}` },
    firstName: { type: String, required: true, trim: true, maxlength: 60 },
    lastName: { type: String, required: true, trim: true, maxlength: 60 },
    name: { type: String, required: true, trim: true },
    email: { type: String, required: true, unique: true, lowercase: true, trim: true, maxlength: 254 },
    passwordHash: { type: String, required: function() { return this.isNew; }, select: false },
    refreshTokenHash: { type: String, default: null, select: false },
    sessionVersion: { type: Number, default: 0 },
    role: { type: String, enum: ['user', 'admin'], default: 'user' },
    profilePicUrl: { type: String, default: '' },
    profile: { type: profileSchema, default: () => ({}) },
    progress: { type: progressSchema, default: () => ({}) },
    weeklyGoals: { type: mongoose.Schema.Types.Mixed, default: () => ({}) },
    lastLogin: { type: Date, default: null }
}, { timestamps: true });

userSchema.set('toJSON', {
    transform: (_document, value) => {
        delete value.passwordHash;
        delete value.refreshTokenHash;
        delete value.__v;
        return value;
    }
});

const MongooseUser = mongoose.models.User || mongoose.model('User', userSchema);
const { inMemoryStore, MemoryUserModel } = require('../inMemoryDb');

function UserProxy(data) {
    if (inMemoryStore.isMemoryMode) {
        return new MemoryUserModel(data);
    }
    return new MongooseUser(data);
}

Object.setPrototypeOf(UserProxy, new Proxy(MongooseUser, {
    get(target, prop) {
        if (inMemoryStore.isMemoryMode && prop in MemoryUserModel) {
            return MemoryUserModel[prop];
        }
        return target[prop];
    }
}));

module.exports = UserProxy;