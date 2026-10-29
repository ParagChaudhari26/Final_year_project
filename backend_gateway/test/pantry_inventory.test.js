const test = require('node:test');
const assert = require('node:assert/strict');
const {
    allocatePantryIngredient,
    deductPantryPlan,
    PantryStockConflict
} = require('../pantry_inventory');

test('allocates matching stock in expiry order and converts kilograms to grams', () => {
    const pantry = [
        { itemId: 'tomato-new', userId: 'user-a', name: 'Tomato', quantity: 0.2, unit: 'kg', daysUntilExpiry: 8 },
        { itemId: 'tomato-expiring', userId: 'user-a', name: 'Tomato', quantity: 50, unit: 'g', daysUntilExpiry: 1 },
        { itemId: 'other-user', userId: 'user-b', name: 'Tomato', quantity: 500, unit: 'g', daysUntilExpiry: 1 }
    ];
    const plan = allocatePantryIngredient(pantry, 'user-a', {
        ingredientId: 'ING_TOMATO', name: 'Tomato', quantity: 150, unit: 'g'
    });

    assert.equal(plan.availableQuantity, 150);
    assert.equal(plan.shortfallQuantity, 0);
    assert.deepEqual(plan.allocations.map(item => item.itemId), ['tomato-expiring', 'tomato-new']);
    assert.equal(plan.allocations[1].quantity, 0.1);
});

test('reports missing quantity without allocating stock from another user', () => {
    const pantry = [
        { itemId: 'own', userId: 'user-a', name: 'Toor Dal', quantity: 50, unit: 'g' },
        { itemId: 'other', userId: 'user-b', name: 'Toor Dal', quantity: 500, unit: 'g' }
    ];
    const plan = allocatePantryIngredient(pantry, 'user-a', {
        ingredientId: 'ING_TOOR_DAL', name: 'Pigeon Pea', quantity: 200, unit: 'g'
    });

    assert.equal(plan.availableQuantity, 50);
    assert.equal(plan.shortfallQuantity, 150);
    assert.deepEqual(plan.allocations.map(item => item.itemId), ['own']);
});

test('deducts allocated quantities, removes exhausted items, and preserves other users', () => {
    const pantry = [
        { itemId: 'rice', userId: 'user-a', name: 'Rice', quantity: 0.2, unit: 'kg' },
        { itemId: 'onion', userId: 'user-a', name: 'Onion', quantity: 100, unit: 'g' },
        { itemId: 'other-user', userId: 'user-b', name: 'Rice', quantity: 10, unit: 'kg' }
    ];
    const plan = [
        { name: 'Basmati Rice', allocations: [{ itemId: 'rice', itemName: 'Rice', quantity: 100, unit: 'g' }] },
        { name: 'Onion', allocations: [{ itemId: 'onion', itemName: 'Onion', quantity: 100, unit: 'g' }] }
    ];
    const result = deductPantryPlan(pantry, 'user-a', plan);

    assert.equal(result.pantry.find(item => item.itemId === 'rice').quantity, 0.1);
    assert.equal(result.pantry.some(item => item.itemId === 'onion'), false);
    assert.equal(result.pantry.find(item => item.itemId === 'other-user').quantity, 10);
    assert.equal(result.consumed.length, 2);
});

test('rejects stale inventory without changing the pantry', () => {
    const pantry = [{ itemId: 'rice', userId: 'user-a', name: 'Rice', quantity: 40, unit: 'g' }];
    const plan = [{ name: 'Basmati Rice', allocations: [{ itemId: 'rice', itemName: 'Rice', quantity: 50, unit: 'g' }] }];

    assert.throws(() => deductPantryPlan(pantry, 'user-a', plan), PantryStockConflict);
    assert.equal(pantry[0].quantity, 40);
});