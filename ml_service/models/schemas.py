from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# ── Shared building blocks ──────────────────────────────────────

class IngredientItem(BaseModel):
    name: str
    ifctCode: Optional[str] = None
    ingredientId: Optional[str] = None
    quantity: Optional[float] = 100.0
    unit: Optional[str] = "g"
    daysUntilExpiry: Optional[int] = 30

class MacroTargets(BaseModel):
    calories: Optional[float] = 2000
    protein: Optional[float] = 80
    carbs: Optional[float] = 250
    fat: Optional[float] = 65

class UserProfile(BaseModel):
    dietType: Optional[str] = "Vegetarian"
    allergies: Optional[List[str]] = []
    healthConditions: Optional[List[str]] = []
    applyAyurvedicConstraints: Optional[bool] = True
    viruddhaStrictMode: Optional[str] = "FILTER"   # FILTER | WARN | OFF
    preferredCuisines: Optional[List[str]] = []
    macroTargets: Optional[MacroTargets] = None

# ── API Request / Response models ───────────────────────────────

class RecommendationRequest(BaseModel):
    userProfile: UserProfile
    pantryItems: List[IngredientItem] = []

class MealPlanRequest(BaseModel):
    preferredCuisines: List[str] = ["Pan-Indian", "Punjabi"]
    days: int = Field(default=7, ge=1, le=14)
    userProfile: Optional[UserProfile] = None

class NutritionCalculateRequest(BaseModel):
    ingredients: List[IngredientItem]
    cookingProcess: Optional[str] = "simmered"
    servings: Optional[int] = 1

class ViruddhaCheckRequest(BaseModel):
    ingredients: List[IngredientItem]
    cookingProcess: Optional[str] = "raw"

class VisionAnalyzeRequest(BaseModel):
    imageData: Optional[str] = None   # base64-encoded image
    mimeType: Optional[str] = "image/jpeg"
    scanType: Optional[str] = "auto"   # "auto" | "receipt" | "food_photo"
    receiptText: Optional[str] = None  # optional text pasted from digital receipt

class ChatMessage(BaseModel):
    role: str    # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    userId: Optional[str] = None
    conversationHistory: Optional[List[ChatMessage]] = []
    language: str = "auto"
    userContext: Optional[Dict[str, Any]] = None

class SpeechSynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="en", pattern="^(en|hi|mr)$")

class CookingGuideRequest(BaseModel):
    recipeId: str = Field(min_length=1, max_length=100)
    servings: Optional[int] = Field(default=None, ge=1, le=20)
    language: str = Field(default="en", pattern="^(en|hi|mr)$")

# ── Response models ──────────────────────────────────────────────

class NutritionInfo(BaseModel):
    calories: float = 0.0
    proteinG: float = 0.0
    carbsG: float = 0.0
    fatG: float = 0.0
    fibreG: float = 0.0
    sodiumMg: float = 0.0
    ironMg: float = 0.0
    calciumMg: float = 0.0

class RecipeRecommendation(BaseModel):
    recipeId: str
    title: str
    cuisine: str
    dietType: str
    score: float
    pantryMatchPct: float
    expiryUrgencyScore: float
    nutritionFitScore: float
    prepTimeMinutes: int
    cookTimeMinutes: int
    difficultyLevel: str
    description: str
    usedIngredients: List[str]
    missingIngredients: List[str]
    beneficiaries: List[str]
    nutritionPerServing: Optional[Dict[str, Any]] = None

class FilteredRecipe(BaseModel):
    recipeId: str
    title: str
    violations: List[Dict[str, str]]
    severity: str

class RecommendationResponse(BaseModel):
    recommended: List[RecipeRecommendation]
    filtered: List[FilteredRecipe]
    totalEvaluated: int

class VisionDetectedItem(BaseModel):
    name: str
    confidence: float
    estimatedQuantity: float
    unit: str
    category: Optional[str] = "Pantry Staples"
    daysUntilExpiry: Optional[int] = 7
    ifctCode: Optional[str] = None
    estimatedCalories: Optional[float] = None

class VisionAnalyzeResponse(BaseModel):
    detectedItems: List[VisionDetectedItem]
    totalEstimatedCalories: float
    processingMethod: str
    message: str

class ChatResponse(BaseModel):
    response: str
    sources: List[str]
    suggestions: List[str]
    confidence: float

class ViruddhaViolation(BaseModel):
    type: str
    severity: str
    reason: str
    ingredients: List[str]
    ayurvedicText: Optional[str] = None

class ViruddhaCheckResponse(BaseModel):
    isCompatible: bool
    overallSeverity: str
    violations: List[ViruddhaViolation]
    recommendations: List[str]
    compatibilityScore: float
