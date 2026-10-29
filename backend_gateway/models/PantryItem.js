const mongoose = require('mongoose');

const pantryItemSchema = new mongoose.Schema({
    itemId: { type: String, required: true },
    userId: { type: String, required: true, index: true },
    ingredientId: { type: String, default: '' },
    name: { type: String, required: true, trim: true, maxlength: 120 },
    quantity: { type: Number, required: true, min: 0 },
    unit: { type: String, required: true, trim: true, default: 'g' },
    daysUntilExpiry: { type: Number, default: 7, min: 0 },
    category: { type: String, default: 'Pantry Staples' },
    ifctCode: { type: String, default: null },
    addedAt: { type: Date, default: Date.now }
}, { timestamps: true });

pantryItemSchema.index({ userId: 1, itemId: 1 }, { unique: true });

const MongoosePantryItem = mongoose.models.PantryItem || mongoose.model('PantryItem', pantryItemSchema);
const { inMemoryStore, MemoryPantryModel } = require('../inMemoryDb');

function PantryItemProxy(data) {
    if (inMemoryStore.isMemoryMode) {
        return MemoryPantryModel.create(data);
    }
    return new MongoosePantryItem(data);
}

Object.setPrototypeOf(PantryItemProxy, new Proxy(MongoosePantryItem, {
    get(target, prop) {
        if (inMemoryStore.isMemoryMode && prop in MemoryPantryModel) {
            return MemoryPantryModel[prop];
        }
        return target[prop];
    }
}));

module.exports = PantryItemProxy;