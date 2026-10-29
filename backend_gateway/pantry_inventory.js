const ingredientAliases = {
    toordal: 'toordal',
    pigeonpea: 'toordal',
    kidneybeans: 'kidneybeans',
    rajma: 'kidneybeans',
    chickpeas: 'chickpeas',
    chana: 'chickpeas',
    flattenedrice: 'flattenedrice',
    poha: 'flattenedrice',
    redlentils: 'redlentils',
    masoordal: 'redlentils',
    yellowmoongdal: 'yellowmoongdal',
    moongdal: 'yellowmoongdal',
    basmatirice: 'basmatirice',
    rice: 'basmatirice',
    curdyogurt: 'yogurt',
    yogurt: 'yogurt',
    curd: 'yogurt'
};

const unitDefinitions = {
    mg: { dimension: 'mass', base: 'g', factor: 0.001 },
    milligram: { dimension: 'mass', base: 'g', factor: 0.001 },
    milligrams: { dimension: 'mass', base: 'g', factor: 0.001 },
    g: { dimension: 'mass', base: 'g', factor: 1 },
    gram: { dimension: 'mass', base: 'g', factor: 1 },
    grams: { dimension: 'mass', base: 'g', factor: 1 },
    kg: { dimension: 'mass', base: 'g', factor: 1000 },
    kilogram: { dimension: 'mass', base: 'g', factor: 1000 },
    kilograms: { dimension: 'mass', base: 'g', factor: 1000 },
    ml: { dimension: 'volume', base: 'ml', factor: 1 },
    milliliter: { dimension: 'volume', base: 'ml', factor: 1 },
    milliliters: { dimension: 'volume', base: 'ml', factor: 1 },
    l: { dimension: 'volume', base: 'ml', factor: 1000 },
    liter: { dimension: 'volume', base: 'ml', factor: 1000 },
    liters: { dimension: 'volume', base: 'ml', factor: 1000 },
    tsp: { dimension: 'volume', base: 'ml', factor: 5 },
    tbsp: { dimension: 'volume', base: 'ml', factor: 15 },
    cup: { dimension: 'volume', base: 'ml', factor: 240 },
    pc: { dimension: 'count', base: 'pc', factor: 1 },
    pcs: { dimension: 'count', base: 'pc', factor: 1 },
    piece: { dimension: 'count', base: 'pc', factor: 1 },
    pieces: { dimension: 'count', base: 'pc', factor: 1 },
    each: { dimension: 'count', base: 'pc', factor: 1 }
};

class PantryStockConflict extends Error {}

function normalizedIngredientName(name) {
    const key = String(name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    return ingredientAliases[key] || key;
}

function quantityInBase(quantity, unit) {
    const normalizedUnit = String(unit || 'g').toLowerCase().trim();
    const definition = unitDefinitions[normalizedUnit] || {
        dimension: `unit:${normalizedUnit}`,
        base: normalizedUnit,
        factor: 1
    };
    return { amount: Number(quantity) * definition.factor, ...definition };
}

function roundQuantity(quantity) {
    return Math.round((quantity + Number.EPSILON) * 1000) / 1000;
}

function allocatePantryIngredient(pantry, userId, ingredient) {
    const required = quantityInBase(ingredient.quantity, ingredient.unit);
    let remaining = required.amount;
    const allocations = [];
    const candidates = pantry
        .filter(item => item.userId === userId && (
            (ingredient.ingredientId && item.ingredientId && item.ingredientId.toUpperCase() === ingredient.ingredientId.toUpperCase()) ||
            normalizedIngredientName(item.name) === normalizedIngredientName(ingredient.name)
        ))
        .sort((left, right) => Number(left.daysUntilExpiry ?? 999) - Number(right.daysUntilExpiry ?? 999));

    for (const item of candidates) {
        if (remaining <= 0) break;
        const available = quantityInBase(item.quantity, item.unit);
        if (available.dimension !== required.dimension || available.amount <= 0) continue;
        const takeBase = Math.min(available.amount, remaining);
        allocations.push({
            itemId: item.itemId,
            itemName: item.name,
            quantity: roundQuantity(takeBase / available.factor),
            unit: item.unit || 'g',
            recipeQuantity: roundQuantity(takeBase / required.factor),
            recipeUnit: ingredient.unit || 'g'
        });
        remaining -= takeBase;
    }

    return {
        ingredientId: ingredient.ingredientId,
        name: ingredient.name,
        requiredQuantity: roundQuantity(Number(ingredient.quantity)),
        unit: ingredient.unit || 'g',
        availableQuantity: roundQuantity((required.amount - remaining) / required.factor),
        shortfallQuantity: roundQuantity(remaining / required.factor),
        allocations
    };
}

function deductPantryPlan(pantry, userId, pantryPlan) {
    const deductions = new Map();
    for (const ingredient of pantryPlan) {
        for (const allocation of ingredient.allocations) {
            const amount = quantityInBase(allocation.quantity, allocation.unit);
            const current = deductions.get(allocation.itemId) || {
                itemId: allocation.itemId,
                itemName: allocation.itemName,
                amount: 0,
                dimension: amount.dimension
            };
            if (current.dimension !== amount.dimension) {
                throw new PantryStockConflict(`Incompatible pantry units for ${allocation.itemName}.`);
            }
            current.amount += amount.amount;
            deductions.set(allocation.itemId, current);
        }
    }

    for (const deduction of deductions.values()) {
        const item = pantry.find(entry => entry.userId === userId && entry.itemId === deduction.itemId);
        if (!item) throw new PantryStockConflict(`${deduction.itemName} is no longer in the pantry.`);
        const available = quantityInBase(item.quantity, item.unit);
        if (available.dimension !== deduction.dimension || available.amount + 0.0001 < deduction.amount) {
            throw new PantryStockConflict(`There is no longer enough ${item.name} in the pantry.`);
        }
    }

    const consumed = [];
    const updatedPantry = [];
    for (const item of pantry) {
        const deduction = item.userId === userId ? deductions.get(item.itemId) : null;
        if (!deduction) {
            updatedPantry.push(item);
            continue;
        }
        const current = quantityInBase(item.quantity, item.unit);
        const remainingQuantity = roundQuantity(Math.max(0, current.amount - deduction.amount) / current.factor);
        consumed.push({
            itemId: item.itemId,
            name: item.name,
            quantity: roundQuantity(deduction.amount / current.factor),
            unit: item.unit || 'g',
            remainingQuantity
        });
        if (remainingQuantity > 0) updatedPantry.push({ ...item, quantity: remainingQuantity });
    }
    return { pantry: updatedPantry, consumed };
}

module.exports = { allocatePantryIngredient, deductPantryPlan, PantryStockConflict };