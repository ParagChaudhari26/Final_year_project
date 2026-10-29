import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:5001/api';
axios.defaults.withCredentials = true;
let tokenRefreshRequest = null;
axios.interceptors.response.use(response => response, async error => {
  const request = error.config;
  const url = request?.url || '';
  const isAuthAction = /\/auth\/(login|register|refresh|logout)/.test(url);
  if (error.response?.status === 401 && request && !request._authRetry && !isAuthAction) {
    request._authRetry = true;
    try {
      tokenRefreshRequest ||= axios.post(`${API_BASE}/auth/refresh`)
        .finally(() => { tokenRefreshRequest = null; });
      await tokenRefreshRequest;
      return axios(request);
    } catch (refreshError) {
      return Promise.reject(refreshError);
    }
  }
  return Promise.reject(error);
});

export default function App() {
  // Navigation & User State
  const [activeTab, setActiveTab] = useState('recommendations');
  const [authUser, setAuthUser] = useState(null);
  const [authStatus, setAuthStatus] = useState('checking');
  const [authMode, setAuthMode] = useState('login');
  const [authForm, setAuthForm] = useState({ firstName: '', lastName: '', email: '', password: '', confirmPassword: '' });
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [currentUser, setCurrentUser] = useState(null);
  const [profileDraft, setProfileDraft] = useState(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileError, setProfileError] = useState('');
  const [systemHealth, setSystemHealth] = useState(null);
  const [gamification, setGamification] = useState(null);
  const [notification, setNotification] = useState(null);

  // Recommendations State
  const [recommendations, setRecommendations] = useState({ recommended: [], filtered: [], totalEvaluated: 0 });
  const [selectedCuisine, setSelectedCuisine] = useState('All');
  const [loadingRecs, setLoadingRecs] = useState(false);

  // Pantry State
  const [pantryItems, setPantryItems] = useState([]);
  const [newPantryItem, setNewPantryItem] = useState({ name: '', quantity: 200, unit: 'g', daysUntilExpiry: 3, category: 'Vegetables' });
  const [loadingPantry, setLoadingPantry] = useState(false);

  // Viruddha Sandbox State
  const [viruddhaSelected, setViruddhaSelected] = useState(['milk', 'lemon']);
  const [customFoodInput, setCustomFoodInput] = useState('');
  const [viruddhaResult, setViruddhaResult] = useState(null);
  const [loadingViruddha, setLoadingViruddha] = useState(false);

  // Meal Plan State
  const [mealPlan, setMealPlan] = useState(null);
  const [selectedPlanDay, setSelectedPlanDay] = useState(1);
  const [loadingPlan, setLoadingPlan] = useState(false);

  // Vision & Supermarket Receipt State
  const [visionImage, setVisionImage] = useState(null);
  const [visionResults, setVisionResults] = useState(null);
  const [loadingVision, setLoadingVision] = useState(false);
  const [scanMode, setScanMode] = useState('receipt'); // 'receipt' | 'food_photo'
  const [receiptTextInput, setReceiptTextInput] = useState('');

  // RAG Chat State
  const [chatMessages, setChatMessages] = useState([
    {
      role: 'assistant',
      content: 'Namaste! I am your FoodCoach AI assistant. I can answer questions on Indian food nutrition (ICMR IFCT 2017), Ayurvedic dietary compatibility (Charaka Samhita), and customized meal planning. How can I assist you today?',
      sources: ['Ayurveda & IFCT Knowledge Base'],
      suggestions: ['Why is milk incompatible with fish?', 'Best Indian foods for iron deficiency?', 'High protein vegetarian plan'],
      language: 'en'
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [loadingChat, setLoadingChat] = useState(false);
  const [chatLanguage, setChatLanguage] = useState('auto');
  const [recordingVoice, setRecordingVoice] = useState(false);
  const [loadingVoice, setLoadingVoice] = useState(false);
  const [playingMessage, setPlayingMessage] = useState(null);
  const [chatError, setChatError] = useState('');
  const recorderRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const audioPlaybackRef = useRef(null);

  // Guided Cooking State
  const [cookingSession, setCookingSession] = useState(null);
  const [cookingRecipeSelection, setCookingRecipeSelection] = useState(null);
  const [cookingStepIndex, setCookingStepIndex] = useState(0);
  const [loadingCooking, setLoadingCooking] = useState(false);
  const [cookingError, setCookingError] = useState('');
  const [cookingLanguage, setCookingLanguage] = useState('en');
  const [confirmCookingComplete, setConfirmCookingComplete] = useState(false);
  const [cookingTimerRemaining, setCookingTimerRemaining] = useState(0);
  const [cookingTimerRunning, setCookingTimerRunning] = useState(false);

  const showNotification = (msg, type = 'success') => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 4000);
  };

  useEffect(() => {
    const currentStep = cookingSession?.steps?.[cookingStepIndex];
    setCookingTimerRemaining(currentStep?.timerSeconds || 0);
    setCookingTimerRunning(false);
    setConfirmCookingComplete(false);
  }, [cookingSession, cookingStepIndex]);

  useEffect(() => {
    if (!cookingTimerRunning) return undefined;
    const timerId = setInterval(() => {
      setCookingTimerRemaining(remaining => {
        if (remaining <= 1) {
          setCookingTimerRunning(false);
          showNotification('Step timer complete. Check the food before continuing.');
          return 0;
        }
        return remaining - 1;
      });
    }, 1000);
    return () => clearInterval(timerId);
  }, [cookingTimerRunning]);

  // ─────────────────────────────────────────────────────────────────────────
  // Initial Load & User Switching
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    // Check system health
    axios.get(`${API_BASE}/health`).then(res => setSystemHealth(res.data)).catch(() => setSystemHealth({ gateway: 'offline' }));

    axios.get(`${API_BASE}/auth/me`).then(res => {
      setAuthUser(res.data.user);
      setSelectedUserId(res.data.user.userId);
      setAuthStatus('authenticated');
    }).catch(() => {
      setAuthUser(null);
      setSelectedUserId('');
      setAuthStatus('unauthenticated');
    });
  }, []);

  useEffect(() => () => {
    audioPlaybackRef.current?.pause();
    mediaStreamRef.current?.getTracks().forEach(track => track.stop());
  }, []);

  useEffect(() => {
    if (!selectedUserId) return;
    // Load active user profile, pantry, gamification, and recommendations
    axios.get(`${API_BASE}/profile/${selectedUserId}`).then(res => setCurrentUser(res.data)).catch(console.error);
    axios.get(`${API_BASE}/gamification/${selectedUserId}`).then(res => setGamification(res.data)).catch(console.error);
    fetchPantry();
    fetchRecommendations();
    fetchMealPlan();
  }, [selectedUserId]);

  useEffect(() => {
    if (!currentUser) return;
    const profile = currentUser.profile || {};
    setProfileDraft({
      firstName: currentUser.firstName || '',
      lastName: currentUser.lastName || '',
      profile: {
        age: profile.age ?? '',
        gender: profile.gender || '',
        heightCm: profile.heightCm ?? '',
        weightKg: profile.weightKg ?? '',
        activityLevel: profile.activityLevel || 'Moderate',
        dietType: profile.dietType || 'Vegetarian',
        allergiesText: (profile.allergies || []).join(', '),
        healthConditions: profile.healthConditions || [],
        preferredCuisines: profile.preferredCuisines || [],
        applyAyurvedicConstraints: profile.applyAyurvedicConstraints !== false,
        viruddhaStrictMode: profile.viruddhaStrictMode || 'FILTER',
        macroTargets: profile.macroTargets || { calories: 2000, protein: 80, carbs: 250, fat: 65 }
      }
    });
  }, [currentUser]);

  const handleAuthSubmit = async event => {
    event.preventDefault();
    setAuthError('');
    if (authMode === 'register' && authForm.password !== authForm.confirmPassword) {
      setAuthError('Passwords do not match.');
      return;
    }
    setAuthLoading(true);
    try {
      const response = await axios.post(`${API_BASE}/auth/${authMode}`, {
        firstName: authForm.firstName,
        lastName: authForm.lastName,
        email: authForm.email,
        password: authForm.password
      });
      const user = response.data.user;
      setAuthUser(user);
      setCurrentUser(user);
      setSelectedUserId(user.userId);
      setAuthStatus('authenticated');
      setActiveTab(authMode === 'register' ? 'profile' : 'recommendations');
      setAuthForm({ firstName: '', lastName: '', email: '', password: '', confirmPassword: '' });
    } catch (error) {
      setAuthError(error.response?.data?.error || 'Could not authenticate. Please try again.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await axios.post(`${API_BASE}/auth/logout`);
    } catch (error) {
      console.warn('Logout request failed; clearing this browser session.', error.message);
    }
    setAuthUser(null);
    setCurrentUser(null);
    setSelectedUserId('');
    setAuthStatus('unauthenticated');
    setActiveTab('recommendations');
  };

  const handleSaveProfile = async event => {
    event.preventDefault();
    if (!profileDraft) return;
    setSavingProfile(true);
    setProfileError('');
    const { profile, ...identity } = profileDraft;
    const toNumberOrNull = value => value === '' || value === null ? null : Number(value);
    const cleanedProfile = {
      ...profile,
      age: toNumberOrNull(profile.age),
      heightCm: toNumberOrNull(profile.heightCm),
      weightKg: toNumberOrNull(profile.weightKg),
      allergies: profile.allergiesText.split(',').map(value => value.trim()).filter(Boolean),
      macroTargets: Object.fromEntries(Object.entries(profile.macroTargets).map(([key, value]) => [key, Number(value)]))
    };
    delete cleanedProfile.allergiesText;
    try {
      const response = await axios.put(`${API_BASE}/profile/${selectedUserId}`, {
        ...identity,
        profile: cleanedProfile
      });
      setCurrentUser(response.data.user);
      setAuthUser(response.data.user);
      showNotification('Profile saved. Recipe recommendations will use these preferences.');
    } catch (error) {
      setProfileError(error.response?.data?.error || 'Could not save your profile.');
    } finally {
      setSavingProfile(false);
    }
  };

  const updateProfileField = (field, value) => {
    setProfileDraft(previous => ({
      ...previous,
      profile: { ...previous.profile, [field]: value }
    }));
  };

  const toggleProfileArrayValue = (field, value) => {
    const values = profileDraft?.profile?.[field] || [];
    updateProfileField(field, values.includes(value)
      ? values.filter(item => item !== value)
      : [...values, value]);
  };

  const fetchPantry = () => {
    setLoadingPantry(true);
    axios.get(`${API_BASE}/pantry/${selectedUserId}`)
      .then(res => setPantryItems(res.data.items || []))
      .catch(console.error)
      .finally(() => setLoadingPantry(false));
  };

  const fetchRecommendations = () => {
    setLoadingRecs(true);
    axios.post(`${API_BASE}/recommendations/${selectedUserId}`)
      .then(res => setRecommendations(res.data))
      .catch(console.error)
      .finally(() => setLoadingRecs(false));
  };

  const fetchMealPlan = () => {
    setLoadingPlan(true);
    axios.post(`${API_BASE}/meal-plan`, {
      preferredCuisines: currentUser?.profile?.preferredCuisines || ['Pan-Indian', 'Punjabi', 'Maharashtrian'],
      days: 7,
      userProfile: currentUser?.profile
    })
      .then(res => setMealPlan(res.data))
      .catch(console.error)
      .finally(() => setLoadingPlan(false));
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Pantry Handlers
  // ─────────────────────────────────────────────────────────────────────────
  const handleAddPantryItem = (e) => {
    e.preventDefault();
    if (!newPantryItem.name.trim()) return;
    axios.post(`${API_BASE}/pantry/${selectedUserId}`, newPantryItem)
      .then(res => {
        showNotification(`Added ${newPantryItem.name} to pantry!`);
        setNewPantryItem({ name: '', quantity: 200, unit: 'g', daysUntilExpiry: 3, category: 'Vegetables' });
        fetchPantry();
        fetchRecommendations();
      })
      .catch(err => showNotification(err.message, 'error'));
  };

  const handleDeletePantryItem = (itemId, name) => {
    axios.delete(`${API_BASE}/pantry/${selectedUserId}/${itemId}`)
      .then(() => {
        showNotification(`Removed ${name} from pantry`);
        fetchPantry();
        fetchRecommendations();
      })
      .catch(err => showNotification(err.message, 'error'));
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Cooking & Gamification Handlers
  // ─────────────────────────────────────────────────────────────────────────
  const startCookingSession = async (recipe, language = cookingLanguage) => {
    setLoadingCooking(true);
    setCookingError('');
    try {
      const response = await axios.post(`${API_BASE}/cooking/guide`, {
        userId: selectedUserId,
        recipeId: recipe.recipeId,
        language
      }, { timeout: 240000 });
      setCookingRecipeSelection(recipe);
      setCookingSession(response.data);
      setCookingStepIndex(0);
    } catch (err) {
      setCookingError(err.response?.data?.error || 'Could not load cooking instructions.');
    } finally {
      setLoadingCooking(false);
    }
  };

  const finishCookingSession = async () => {
    if (!cookingSession || !confirmCookingComplete) return;
    setLoadingCooking(true);
    setCookingError('');
    audioPlaybackRef.current?.pause();
    try {
      const response = await axios.post(`${API_BASE}/cooking/complete`, {
        userId: selectedUserId,
        sessionId: cookingSession.sessionId,
        confirmed: true
      });
      const usedText = response.data.consumed?.length
        ? response.data.consumed.map(item => `${item.quantity} ${item.unit} ${item.name}`).join(', ')
        : 'No pantry quantities needed deduction';
      setCookingSession(null);
      setCookingRecipeSelection(null);
      setPlayingMessage(null);
      showNotification(`Pantry updated: ${usedText}. +${response.data.awardedPoints} points.`);
      fetchPantry();
      fetchRecommendations();
      axios.get(`${API_BASE}/gamification/${selectedUserId}`).then(result => setGamification(result.data));
    } catch (err) {
      setCookingError(err.response?.data?.error || 'Could not update pantry after cooking. Please retry.');
    } finally {
      setLoadingCooking(false);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Viruddha Ahaar Sandbox Handlers
  // ─────────────────────────────────────────────────────────────────────────
  const handleCheckViruddha = (itemsToCheck) => {
    setLoadingViruddha(true);
    const payload = (itemsToCheck || viruddhaSelected).map(name => ({ name }));
    axios.post(`${API_BASE}/viruddha-check`, { ingredients: payload, cookingProcess: 'raw' })
      .then(res => setViruddhaResult(res.data))
      .catch(console.error)
      .finally(() => setLoadingViruddha(false));
  };

  const handleAddCustomFood = (e) => {
    e.preventDefault();
    if (!customFoodInput.trim()) return;
    const item = customFoodInput.trim().toLowerCase();
    if (!viruddhaSelected.includes(item)) {
      const updated = [...viruddhaSelected, item];
      setViruddhaSelected(updated);
      handleCheckViruddha(updated);
    }
    setCustomFoodInput('');
  };

  const handleRemoveViruddhaItem = (itemToRemove) => {
    const updated = viruddhaSelected.filter(i => i !== itemToRemove);
    setViruddhaSelected(updated);
    if (updated.length >= 2) handleCheckViruddha(updated);
    else setViruddhaResult(null);
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Vision Scanner Handlers
  // ─────────────────────────────────────────────────────────────────────────
  const handleSimulateScan = (foodType) => {
    setLoadingVision(true);
    const samplePng = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
    axios.post(`${API_BASE}/vision/analyze`, { imageData: samplePng, mimeType: 'image/png', scanType: 'food_photo' })
      .then(res => {
        if (res.data.detectedItems.length === 0) {
          const mockDetections = foodType === 'greens' ? [
            { name: 'Spinach', confidence: 0.94, estimatedQuantity: 250, unit: 'g', category: 'Leafy Vegetables', daysUntilExpiry: 2, ifctCode: 'A063', estimatedCalories: 65.0 },
            { name: 'Paneer', confidence: 0.89, estimatedQuantity: 200, unit: 'g', category: 'Dairy', daysUntilExpiry: 3, ifctCode: 'E005', estimatedCalories: 530.0 },
            { name: 'Tomato', confidence: 0.92, estimatedQuantity: 150, unit: 'g', category: 'Vegetables', daysUntilExpiry: 4, ifctCode: 'B076', estimatedCalories: 30.0 }
          ] : [
            { name: 'Chickpea', confidence: 0.91, estimatedQuantity: 300, unit: 'g', category: 'Pulses', daysUntilExpiry: 180, ifctCode: 'C009', estimatedCalories: 1080.0 },
            { name: 'Onion', confidence: 0.88, estimatedQuantity: 200, unit: 'g', category: 'Vegetables', daysUntilExpiry: 14, ifctCode: 'B060', estimatedCalories: 100.0 },
            { name: 'Potato', confidence: 0.95, estimatedQuantity: 400, unit: 'g', category: 'Vegetables', daysUntilExpiry: 14, ifctCode: 'B063', estimatedCalories: 388.0 }
          ];
          setVisionResults({
            detectedItems: mockDetections,
            totalEstimatedCalories: mockDetections.reduce((acc, i) => acc + i.estimatedCalories, 0),
            processingMethod: 'Interactive Food Photo Recognizer (IFCT 2017)',
            message: `Detected ${mockDetections.length} items with nutritional indexing.`
          });
        } else {
          setVisionResults(res.data);
        }
      })
      .catch(err => showNotification(err.message, 'error'))
      .finally(() => setLoadingVision(false));
  };

  const handleScanReceipt = (customText) => {
    setLoadingVision(true);
    const textToScan = customText !== undefined ? customText : receiptTextInput;
    axios.post(`${API_BASE}/vision/analyze`, {
      scanType: 'receipt',
      receiptText: textToScan || undefined
    })
      .then(res => setVisionResults(res.data))
      .catch(err => showNotification(err.message, 'error'))
      .finally(() => setLoadingVision(false));
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64Data = reader.result.split(',')[1];
      setLoadingVision(true);
      axios.post(`${API_BASE}/vision/analyze`, {
        imageData: base64Data,
        mimeType: file.type || 'image/jpeg',
        scanType: scanMode
      })
        .then(res => setVisionResults(res.data))
        .catch(err => showNotification(err.message, 'error'))
        .finally(() => setLoadingVision(false));
    };
    reader.readAsDataURL(file);
  };

  const handleImportVisionToPantry = () => {
    if (!visionResults?.detectedItems) return;
    let addedCount = 0;
    visionResults.detectedItems.forEach(item => {
      axios.post(`${API_BASE}/pantry/${selectedUserId}`, {
        name: item.name,
        quantity: item.estimatedQuantity,
        unit: item.unit,
        daysUntilExpiry: item.daysUntilExpiry || 7,
        category: item.category || 'Scanned Items',
        ifctCode: item.ifctCode
      }).then(() => {
        addedCount++;
        if (addedCount === visionResults.detectedItems.length) {
          showNotification(`Added ${addedCount} items to your pantry!`);
          fetchPantry();
          fetchRecommendations();
          axios.post(`${API_BASE}/gamification/event`, { userId: selectedUserId, type: 'PANTRY_SCAN' })
            .then(() => axios.get(`${API_BASE}/gamification/${selectedUserId}`).then(g => setGamification(g.data)));
        }
      });
    });
  };

  // ─────────────────────────────────────────────────────────────────────────
  // RAG Chatbot Handlers
  // ─────────────────────────────────────────────────────────────────────────
  const handleSendChat = (messageText, requestedLanguage = chatLanguage) => {
    const text = messageText || chatInput;
    if (!text.trim()) return;

    const userMsg = { role: 'user', content: text };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setLoadingChat(true);
    setChatError('');

    const userContext = {
      dietType: currentUser?.profile?.dietType,
      allergies: currentUser?.profile?.allergies || [],
      healthConditions: currentUser?.profile?.healthConditions || [],
      pantryItems: pantryItems.map(item => item.name),
      recommendedRecipes: (recommendations.recommended || []).slice(0, 8).map(recipe => ({
        title: recipe.title,
        usedIngredients: recipe.usedIngredients,
        missingIngredients: recipe.missingIngredients
      }))
    };

    axios.post(`${API_BASE}/chat`, {
      message: text,
      language: requestedLanguage,
      userId: selectedUserId,
      userContext,
      conversationHistory: chatMessages.slice(-6)
    }, { timeout: 240000 }).then(res => {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.response,
        sources: res.data.sources,
        suggestions: res.data.suggestions,
        confidence: res.data.confidence,
        provider: res.data.provider,
        language: res.data.language || (['en', 'hi', 'mr'].includes(requestedLanguage) ? requestedLanguage : 'en')
      }]);
    }).catch(err => {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error connecting to FoodCoach assistant: ${err.response?.data?.error || err.message}`,
        sources: [],
        suggestions: []
      }]);
    }).finally(() => setLoadingChat(false));
  };

  const handleToggleVoiceInput = async () => {
    if (recordingVoice) {
      recorderRef.current?.stop();
      setRecordingVoice(false);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setChatError('Voice recording is not supported by this browser. Try a recent version of Chrome or Edge.');
      return;
    }

    try {
      setChatError('');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const preferredType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : undefined;
      const recorder = new MediaRecorder(stream, preferredType ? { mimeType: preferredType } : undefined);
      const chunks = [];
      recorderRef.current = recorder;
      recorder.ondataavailable = event => {
        if (event.data.size) chunks.push(event.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());
        mediaStreamRef.current = null;
        recorderRef.current = null;
        setRecordingVoice(false);
        const recording = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
        if (!recording.size) {
          setChatError('No audio was recorded. Please try again.');
          return;
        }

        setLoadingVoice(true);
        try {
          const result = await axios.post(`${API_BASE}/voice/transcribe`, recording, {
            headers: {
              'Content-Type': recording.type,
              'X-Language': chatLanguage
            },
            timeout: 180000
          });
          const detectedLanguage = ['en', 'hi', 'mr'].includes(result.data.language)
            ? result.data.language
            : 'en';
          if (!result.data.text?.trim()) {
            setChatError('I could not hear any words. Please try recording again.');
            return;
          }
          handleSendChat(result.data.text, detectedLanguage);
        } catch (err) {
          setChatError(err.response?.data?.error || 'Speech recognition failed. Check that the Whisper service is available.');
        } finally {
          setLoadingVoice(false);
        }
      };
      recorder.start();
      setRecordingVoice(true);
    } catch (err) {
      setChatError(err.message || 'Microphone access was denied.');
      mediaStreamRef.current?.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
  };

  const handleSpeakReply = async (text, language = 'en', setError = setChatError) => {
    const outputLanguage = ['en', 'hi', 'mr'].includes(language) ? language : 'en';
    setError('');
    if (playingMessage === text) {
      audioPlaybackRef.current?.pause();
      window.speechSynthesis?.cancel();
      audioPlaybackRef.current = null;
      setPlayingMessage(null);
      return;
    }
    audioPlaybackRef.current?.pause();
    window.speechSynthesis?.cancel();
    setPlayingMessage(text);
    try {
      const result = await axios.post(`${API_BASE}/voice/synthesize`, {
        text: text.replace(/\[([A-Z]+\d+)\]/g, '').replace(/[*_`#]/g, ''),
        language: outputLanguage
      }, { responseType: 'blob', timeout: 180000 });
      const objectUrl = URL.createObjectURL(result.data);
      const audio = new Audio(objectUrl);
      audioPlaybackRef.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(objectUrl);
        setPlayingMessage(null);
        audioPlaybackRef.current = null;
      };
      audio.onerror = () => {
        URL.revokeObjectURL(objectUrl);
        setPlayingMessage(null);
        audioPlaybackRef.current = null;
        setError('Could not play the generated voice response.');
      };
      await audio.play();
    } catch (err) {
      if ('speechSynthesis' in window && 'SpeechSynthesisUtterance' in window) {
        const utterance = new SpeechSynthesisUtterance(text.replace(/\[([A-Z]+\d+)\]/g, '').replace(/[*_`#]/g, ''));
        utterance.lang = { en: 'en-IN', hi: 'hi-IN', mr: 'mr-IN' }[outputLanguage];
        const browserVoice = window.speechSynthesis.getVoices().find(voice =>
          voice.lang.toLowerCase().startsWith(outputLanguage)
        );
        if (browserVoice) utterance.voice = browserVoice;
        utterance.onend = () => setPlayingMessage(null);
        utterance.onerror = () => {
          setPlayingMessage(null);
          setError('No browser voice is available for this language. Start the optional TTS service.');
        };
        window.speechSynthesis.speak(utterance);
        return;
      }
      setPlayingMessage(null);
      setError(err.response?.data?.error || 'Speech synthesis is unavailable. Start the optional voice service to enable playback.');
    }
  };

  // Filter recommendations by cuisine
  const filteredRecs = recommendations.recommended?.filter(r => {
    if (selectedCuisine === 'All') return true;
    return r.cuisine?.toLowerCase() === selectedCuisine.toLowerCase();
  }) || [];

  if (authStatus === 'checking') {
    return <div className="min-h-screen flex items-center justify-center bg-slate-50 text-sm text-slate-600">Checking your session...</div>;
  }

  if (authStatus !== 'authenticated') {
    const registering = authMode === 'register';
    return (
      <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col">
        <header className="bg-white border-b border-slate-200 px-5 py-4">
          <div className="max-w-6xl mx-auto flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-700 flex items-center justify-center text-white text-xl">🌿</div>
            <div>
              <h1 className="font-bold text-slate-900">FoodCoach AI</h1>
              <p className="text-xs text-slate-500">Your kitchen, your nutrition profile</p>
            </div>
          </div>
        </header>
        <main className="flex-1 max-w-6xl w-full mx-auto grid lg:grid-cols-[1fr_420px] gap-10 items-center px-5 py-10">
          <section className="max-w-xl">
            <p className="text-xs font-bold uppercase text-emerald-700">FoodCoach account</p>
            <h2 className="text-3xl font-bold text-slate-900 mt-3">{registering ? 'Create your profile' : 'Welcome back'}</h2>
            <p className="text-sm leading-6 text-slate-600 mt-3">
              {registering
                ? 'Save your dietary needs and health goals so recipe recommendations fit you.'
                : 'Sign in to access your pantry, personalized recipes, and cooking guide.'}
            </p>
            <div className="grid sm:grid-cols-3 gap-3 mt-8 text-xs">
              <div className="border-l-2 border-emerald-600 pl-3 py-1"><b className="block text-slate-800">Your pantry</b><span className="text-slate-500">Private ingredient tracking</span></div>
              <div className="border-l-2 border-amber-500 pl-3 py-1"><b className="block text-slate-800">Your preferences</b><span className="text-slate-500">Diet, allergies, and goals</span></div>
              <div className="border-l-2 border-sky-600 pl-3 py-1"><b className="block text-slate-800">Your recipes</b><span className="text-slate-500">Recommendations for you</span></div>
            </div>
          </section>
          <form onSubmit={handleAuthSubmit} className="bg-white border border-slate-200 rounded-xl shadow-sm p-6 space-y-4">
            <div>
              <h3 className="font-bold text-slate-900">{registering ? 'Register' : 'Sign in'}</h3>
              <p className="text-xs text-slate-500 mt-1">{registering ? 'Use a valid email and a strong password.' : 'Enter your account credentials.'}</p>
            </div>
            {registering && (
              <div className="grid grid-cols-2 gap-3">
                <label className="text-xs text-slate-600">First name
                  <input value={authForm.firstName} onChange={event => setAuthForm({ ...authForm, firstName: event.target.value })} autoComplete="given-name" required maxLength={60} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
                </label>
                <label className="text-xs text-slate-600">Last name
                  <input value={authForm.lastName} onChange={event => setAuthForm({ ...authForm, lastName: event.target.value })} autoComplete="family-name" required maxLength={60} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
                </label>
              </div>
            )}
            <label className="block text-xs text-slate-600">Email
              <input type="email" value={authForm.email} onChange={event => setAuthForm({ ...authForm, email: event.target.value })} autoComplete="email" required maxLength={254} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
            </label>
            <label className="block text-xs text-slate-600">Password
              <input type="password" value={authForm.password} onChange={event => setAuthForm({ ...authForm, password: event.target.value })} autoComplete={registering ? 'new-password' : 'current-password'} required minLength={8} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
              {registering && <span className="block mt-1 text-[10px] text-slate-500">At least 8 characters, including uppercase, lowercase, a number, and a symbol.</span>}
            </label>
            {registering && (
              <label className="block text-xs text-slate-600">Confirm password
                <input type="password" value={authForm.confirmPassword} onChange={event => setAuthForm({ ...authForm, confirmPassword: event.target.value })} autoComplete="new-password" required minLength={8} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
              </label>
            )}
            {authError && <p role="alert" className="text-xs text-red-700">{authError}</p>}
            <button type="submit" disabled={authLoading} className="w-full bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg py-3 text-sm font-semibold disabled:opacity-50">
              {authLoading ? 'Please wait...' : registering ? 'Create account' : 'Sign in'}
            </button>
            <p className="text-xs text-center text-slate-600">
              {registering ? 'Already registered?' : 'New to FoodCoach?'}{' '}
              <button type="button" className="text-emerald-800 font-semibold underline" onClick={() => { setAuthError(''); setAuthMode(registering ? 'login' : 'register'); }}>
                {registering ? 'Sign in' : 'Create an account'}
              </button>
            </p>
          </form>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col">
      {/* Toast Notification */}
      {notification && (
        <div className={`fixed top-4 right-4 z-50 px-5 py-3 rounded-xl shadow-lg border text-sm font-medium transition-all ${
          notification.type === 'error' ? 'bg-red-50 text-red-800 border-red-200' : 'bg-emerald-50 text-emerald-800 border-emerald-200'
        }`}>
          {notification.msg}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Top Header & User Selector Bar */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
          {/* Logo & Subtitle */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-white text-xl shadow-md font-bold">
              🌿
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-xl font-bold tracking-tight text-slate-900 font-display">FoodCoach AI</h1>
                <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                  Full-Stack v2.0
                </span>
              </div>
              <p className="text-xs text-slate-500">Ayurvedic Viruddha Ahaar Safety • GNN Recipe Graph • IFCT 2017</p>
            </div>
          </div>

          {/* Gamification & User Bar */}
          <div className="flex items-center space-x-4">
            {/* System Pulse */}
            <div className="hidden md:flex items-center space-x-1.5 text-xs text-slate-600 bg-slate-100 px-3 py-1.5 rounded-full">
              <span className={`w-2 h-2 rounded-full ${systemHealth?.gateway === 'healthy' ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`}></span>
              <span>{systemHealth?.mlService?.neo4jConnected ? 'Graph + ML Connected' : 'ML Engine Online'}</span>
            </div>

            {/* Gamification Stats */}
            {gamification && (
              <div className="flex items-center space-x-3 bg-emerald-50 border border-emerald-200 px-3.5 py-1.5 rounded-xl text-xs">
                <div className="flex items-center space-x-1 font-semibold text-emerald-800">
                  <span>🔥</span>
                  <span>{gamification.progress.currentStreak}d Streak</span>
                </div>
                <div className="h-3 w-px bg-emerald-200"></div>
                <div className="font-semibold text-emerald-900">
                  ⭐ Level {gamification.progress.level} ({gamification.progress.points} pts)
                </div>
              </div>
            )}

            {/* Signed-in account */}
            <div className="flex items-center gap-2">
              <button onClick={() => setActiveTab('profile')} className="text-left px-3 py-1.5 rounded-lg hover:bg-slate-100">
                <span className="block text-xs font-semibold text-slate-800">{authUser?.name}</span>
                <span className="block text-[10px] text-slate-500">{authUser?.email}</span>
              </button>
              <button onClick={handleLogout} className="px-3 py-2 rounded-lg border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50">Sign out</button>
            </div>
          </div>
        </div>

        {/* User Constraints Strip */}
        {currentUser && (
          <div className="bg-slate-50 border-t border-slate-100 px-4 sm:px-6 lg:px-8 py-2 text-xs text-slate-600 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-slate-700">Active Profile:</span>
              <span className="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-medium">{currentUser.profile.dietType}</span>
              {currentUser.profile.allergies?.map((a, i) => (
                <span key={i} className="bg-red-100 text-red-800 px-2 py-0.5 rounded font-medium">Allergy: {a}</span>
              ))}
              {currentUser.profile.healthConditions?.map((h, i) => (
                <span key={i} className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded font-medium">{h.replace('HC_', '')}</span>
              ))}
            </div>
            <div className="flex items-center space-x-3 text-slate-500">
              <span>Target: <b>{currentUser.profile.macroTargets?.calories} kcal</b> | <b>{currentUser.profile.macroTargets?.protein}g P</b></span>
              <span>Ayurveda Mode: <b className="text-emerald-700">{currentUser.profile.viruddhaStrictMode}</b></span>
            </div>
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex space-x-1 border-t border-slate-200 overflow-x-auto">
          {[
            { id: 'recommendations', label: 'Smart Recipes (GNN)', icon: '🍲' },
            { id: 'viruddha', label: 'Ayurvedic Safety & Sandbox', icon: '⚖️' },
            { id: 'pantry', label: 'Smart Pantry & Expiry', icon: '🥫' },
            { id: 'meal_plan', label: '7-Day Meal Planner', icon: '📅' },
            { id: 'vision', label: 'AI Vision Scanner', icon: '📷' },
            { id: 'profile', label: 'My Profile', icon: '👤' },
            { id: 'chatbot', label: 'RAG Food Coach', icon: '💬' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 px-4 py-3 border-b-2 text-sm font-medium whitespace-nowrap transition-all ${
                activeTab === tab.id
                  ? 'border-emerald-600 text-emerald-700 font-semibold bg-emerald-50/50'
                  : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
              }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      </header>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Main Content Area */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full">

        {cookingSession && (() => {
          const currentStep = cookingSession.steps[cookingStepIndex];
          const stepCount = cookingSession.steps.length;
          const stepProgress = ((cookingStepIndex + 1) / stepCount) * 100;
          const formatTimer = totalSeconds => `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, '0')}`;

          return (
            <div className="fixed inset-0 z-[60] bg-slate-950/60 p-3 sm:p-6 overflow-y-auto" role="presentation">
              <section
                role="dialog"
                aria-modal="true"
                aria-labelledby="cooking-session-title"
                className="max-w-5xl min-h-[min(90vh,760px)] mx-auto my-2 sm:my-6 bg-slate-50 rounded-2xl shadow-2xl overflow-hidden flex flex-col"
              >
                <header className="bg-emerald-900 text-white px-5 py-4 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-[10px] uppercase font-semibold text-emerald-200">Guided cooking · {cookingSession.servings} servings</p>
                    <h2 id="cooking-session-title" className="text-lg font-bold truncate">{cookingSession.title}</h2>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <select
                      aria-label="Cooking guide language"
                      value={cookingLanguage}
                      onChange={event => {
                        setCookingLanguage(event.target.value);
                        startCookingSession(cookingRecipeSelection, event.target.value);
                      }}
                      className="text-xs text-slate-900 rounded-lg px-2 py-2"
                    >
                      <option value="en">English</option>
                      <option value="hi">Hindi</option>
                      <option value="mr">Marathi</option>
                    </select>
                    <button
                      type="button"
                      title="Close cooking guide"
                      aria-label="Close cooking guide"
                      onClick={() => {
                        audioPlaybackRef.current?.pause();
                        setPlayingMessage(null);
                        setCookingSession(null);
                        setCookingRecipeSelection(null);
                      }}
                      className="w-9 h-9 rounded-lg border border-emerald-700 hover:bg-emerald-800"
                    >
                      ×
                    </button>
                  </div>
                </header>

                <div className="px-5 pt-4">
                  <div className="flex justify-between text-[11px] text-slate-500 mb-1.5">
                    <span>Step {cookingStepIndex + 1} of {stepCount}</span>
                    <span>{cookingSession.steps.reduce((total, step) => total + (step.timerSeconds || 0), 0) > 0 ? `${cookingSession.prepTimeMinutes || 0} min prep · ${cookingSession.cookTimeMinutes || 0} min cook` : 'Follow each step at your own pace'}</span>
                  </div>
                  <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-600 transition-all" style={{ width: `${stepProgress}%` }} />
                  </div>
                </div>

                <div className="grid lg:grid-cols-[minmax(0,1.5fr)_minmax(260px,0.8fr)] gap-5 p-5 flex-1">
                  <div className="space-y-4">
                    <div className="min-h-56 sm:min-h-72 rounded-xl border border-emerald-100 bg-gradient-to-br from-emerald-50 via-white to-amber-50 flex flex-col items-center justify-center text-center p-6">
                      <div className="w-32 h-32 sm:w-40 sm:h-40 rounded-full bg-white border border-emerald-100 shadow-sm flex items-center justify-center text-7xl sm:text-8xl" aria-hidden="true">
                        {currentStep.visual}
                      </div>
                      <span className="mt-4 text-[10px] uppercase tracking-wide text-emerald-700 font-semibold">Cooking step visual</span>
                    </div>
                    <div className="bg-white border border-slate-200 rounded-xl p-5">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-[10px] uppercase text-emerald-700 font-semibold">Step {cookingStepIndex + 1}</p>
                          <h3 className="text-lg font-bold text-slate-900 mt-1">{currentStep.title}</h3>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleSpeakReply(currentStep.instruction, cookingSession.language, setCookingError)}
                          title={playingMessage === currentStep.instruction ? 'Stop narration' : 'Read step aloud'}
                          aria-label={playingMessage === currentStep.instruction ? 'Stop narration' : 'Read step aloud'}
                          className="shrink-0 px-3 py-2 rounded-lg border border-emerald-200 text-emerald-800 hover:bg-emerald-50 text-xs font-semibold"
                        >
                          {playingMessage === currentStep.instruction ? '■ Stop' : '🔊 Read aloud'}
                        </button>
                      </div>
                      <p className="text-sm text-slate-700 leading-relaxed mt-3">{currentStep.instruction}</p>
                      {currentStep.timerSeconds > 0 && (
                        <div className="mt-4 flex items-center gap-3 border-t border-slate-100 pt-4">
                          <span className="font-mono text-lg font-bold text-slate-800">{formatTimer(cookingTimerRemaining)}</span>
                          <button
                            type="button"
                            onClick={() => setCookingTimerRunning(value => !value)}
                            disabled={cookingTimerRemaining === 0}
                            className="px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-semibold disabled:opacity-50"
                          >
                            {cookingTimerRunning ? 'Pause timer' : cookingTimerRemaining === currentStep.timerSeconds ? 'Start timer' : 'Resume timer'}
                          </button>
                          <span className="text-[10px] text-slate-500">Check the food when it ends.</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <aside className="bg-white border border-slate-200 rounded-xl p-4 self-start">
                    <h3 className="text-sm font-bold text-slate-900">Ingredients for {cookingSession.servings}</h3>
                    <div className="mt-3 space-y-2 max-h-64 overflow-y-auto">
                      {cookingSession.pantryPlan.map(item => (
                        <div key={item.ingredientId || item.name} className="flex items-start justify-between gap-3 text-xs border-b border-slate-100 pb-2">
                          <span className="text-slate-700">{item.name}</span>
                          <span className="text-right shrink-0">
                            <b className="text-slate-900">{item.requiredQuantity} {item.unit}</b>
                            <span className={`block text-[10px] ${item.shortfallQuantity > 0 ? 'text-amber-700' : 'text-emerald-700'}`}>
                              {item.shortfallQuantity > 0
                                ? `${item.availableQuantity} available · ${item.shortfallQuantity} short`
                                : `${item.availableQuantity} available`}
                            </span>
                          </span>
                        </div>
                      ))}
                    </div>
                    <p className="mt-3 text-[10px] leading-relaxed text-slate-500">
                      Only available pantry quantities are deducted after you confirm completion. Missing amounts are not deducted.
                    </p>

                    {cookingStepIndex === stepCount - 1 && (
                      <label className="mt-4 flex items-start gap-2 text-xs text-slate-700 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={confirmCookingComplete}
                          onChange={event => setConfirmCookingComplete(event.target.checked)}
                          className="mt-0.5 accent-emerald-700"
                        />
                        <span>I finished cooking this recipe.</span>
                      </label>
                    )}
                  </aside>
                </div>

                {(cookingError || chatError) && <p role="alert" className="px-5 text-xs text-red-700">{cookingError || chatError}</p>}
                <footer className="bg-white border-t border-slate-200 px-5 py-4 flex items-center justify-between gap-3">
                  <button
                    type="button"
                    onClick={() => setCookingStepIndex(index => Math.max(0, index - 1))}
                    disabled={cookingStepIndex === 0 || loadingCooking}
                    className="px-4 py-2 rounded-lg border border-slate-200 text-xs font-semibold disabled:opacity-40"
                  >
                    Previous step
                  </button>
                  {cookingStepIndex < stepCount - 1 ? (
                    <button
                      type="button"
                      onClick={() => setCookingStepIndex(index => Math.min(stepCount - 1, index + 1))}
                      className="px-4 py-2 rounded-lg bg-emerald-700 text-white text-xs font-semibold hover:bg-emerald-800"
                    >
                      Next step
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={finishCookingSession}
                      disabled={!confirmCookingComplete || loadingCooking}
                      className="px-4 py-2 rounded-lg bg-emerald-700 text-white text-xs font-semibold hover:bg-emerald-800 disabled:opacity-40"
                    >
                      {loadingCooking ? 'Updating pantry...' : 'Finish and update pantry'}
                    </button>
                  )}
                </footer>
              </section>
            </div>
          );
        })()}

        {/* ═════════════════════════════════════════════════════════════════ */}
        {/* TAB 1: SMART RECIPE RECOMMENDATIONS (GNN) */}
        {/* ═════════════════════════════════════════════════════════════════ */}
        {activeTab === 'recommendations' && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-2xl shadow-sm border border-slate-200">
              <div>
                <h2 className="text-lg font-bold text-slate-900 font-display">GNN-Ranked Recipes for Your Pantry</h2>
                <p className="text-xs text-slate-500">
                  Scored via 4-factor objective: Pantry match % + Expiry urgency boost + Macro nutrition fitness + PageRank graph connectivity.
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-semibold text-slate-500">Cuisine:</span>
                {['All', 'Punjabi', 'Maharashtrian', 'South Indian', 'Pan-Indian', 'Gujarati'].map(c => (
                  <button
                    key={c}
                    onClick={() => setSelectedCuisine(c)}
                    className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                      selectedCuisine === c
                        ? 'bg-emerald-600 text-white shadow-sm'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            {loadingRecs ? (
              <div className="py-20 text-center text-slate-400">Loading intelligent recommendations...</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredRecs.map((recipe, idx) => (
                  <div key={idx} className="bg-white rounded-2xl shadow-sm border border-slate-200 hover:shadow-md transition-all flex flex-col justify-between overflow-hidden">
                    <div className="p-5">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                              {recipe.cuisine}
                            </span>
                            <span className="text-[10px] text-slate-500">⏱️ {recipe.prepTimeMinutes + recipe.cookTimeMinutes} mins</span>
                          </div>
                          <h3 className="text-base font-bold text-slate-900 font-display">{recipe.title}</h3>
                        </div>
                        <div className="text-right">
                          <span className="text-lg font-extrabold text-emerald-600 font-display">{(recipe.score * 100).toFixed(0)}%</span>
                          <span className="block text-[10px] text-slate-400">Fit Score</span>
                        </div>
                      </div>

                      <p className="mt-2 text-xs text-slate-600 line-clamp-2">{recipe.description}</p>

                      {/* Score Metrics */}
                      <div className="mt-4 grid grid-cols-3 gap-2 bg-slate-50 p-2.5 rounded-xl text-center text-[11px]">
                        <div>
                          <span className="block font-bold text-slate-700">{recipe.pantryMatchPct.toFixed(0)}%</span>
                          <span className="text-slate-400 text-[10px]">Pantry Match</span>
                        </div>
                        <div>
                          <span className="block font-bold text-amber-600">{recipe.expiryUrgencyScore > 0 ? `+${(recipe.expiryUrgencyScore * 100).toFixed(0)}%` : '0%'}</span>
                          <span className="text-slate-400 text-[10px]">Expiry Urgency</span>
                        </div>
                        <div>
                          <span className="block font-bold text-blue-600">{(recipe.nutritionFitScore * 100).toFixed(0)}%</span>
                          <span className="text-slate-400 text-[10px]">Macro Fit</span>
                        </div>
                      </div>

                      {/* Nutrition Macro Badges */}
                      {recipe.nutritionPerServing && (
                        <div className="mt-3 flex items-center justify-between text-[11px] text-slate-600 border-t border-slate-100 pt-2.5">
                          <span>🔥 <b>{recipe.nutritionPerServing.calories}</b> kcal</span>
                          <span>🥩 <b>{recipe.nutritionPerServing.proteinG}g</b> Protein</span>
                          <span>🌾 <b>{recipe.nutritionPerServing.carbsG}g</b> Carbs</span>
                          <span>🥑 <b>{recipe.nutritionPerServing.fatG}g</b> Fat</span>
                        </div>
                      )}

                      {/* Ingredients Used & Missing */}
                      <div className="mt-4 space-y-1.5 text-xs">
                        <div className="flex flex-wrap items-center gap-1">
                          <span className="text-[10px] font-semibold text-emerald-800">In Pantry:</span>
                          {recipe.usedIngredients.map((ing, i) => (
                            <span key={i} className="bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded text-[11px] font-medium border border-emerald-100">
                              ✓ {ing}
                            </span>
                          ))}
                        </div>
                        {recipe.missingIngredients.length > 0 && (
                          <div className="flex flex-wrap items-center gap-1">
                            <span className="text-[10px] font-semibold text-amber-800">Missing:</span>
                            {recipe.missingIngredients.map((ing, i) => (
                              <span key={i} className="bg-amber-50 text-amber-700 px-2 py-0.5 rounded text-[11px] font-medium border border-amber-100">
                                + {ing}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Action Button */}
                    <div className="bg-slate-50 border-t border-slate-100 p-3 flex items-center justify-between">
                      <span className="text-[11px] text-slate-500">Difficulty: <b>{recipe.difficultyLevel}</b></span>
                      <button
                        onClick={() => startCookingSession(recipe)}
                        disabled={loadingCooking}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-3.5 py-1.5 rounded-lg shadow-sm transition-all flex items-center space-x-1 disabled:opacity-50"
                      >
                        <span>{loadingCooking ? 'Loading guide...' : '🍳 Start guided cooking'}</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Viruddha Filtered Section */}
            {recommendations.filtered?.length > 0 && (
              <div className="mt-8 bg-white p-6 rounded-2xl shadow-sm border border-red-200">
                <div className="flex items-center space-x-2 text-red-600 mb-2">
                  <span className="text-xl">⚠️</span>
                  <h3 className="text-base font-bold font-display">Ayurvedically Disqualified Recipes (Viruddha Ahaar Protection)</h3>
                </div>
                <p className="text-xs text-slate-600 mb-4">
                  These recipes were excluded from recommendations because their ingredient combinations create biological incompatibility according to classical texts (Charaka Samhita).
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {recommendations.filtered.map((r, i) => (
                    <div key={i} className="bg-red-50/60 border border-red-200 p-4 rounded-xl">
                      <div className="flex items-center justify-between">
                        <h4 className="font-bold text-red-900 text-sm">{r.title}</h4>
                        <span className="text-[10px] uppercase font-bold bg-red-200 text-red-800 px-2 py-0.5 rounded">
                          {r.severity} Conflict
                        </span>
                      </div>
                      <div className="mt-2 space-y-1">
                        {r.violations?.map((v, idx) => (
                          <div key={idx} className="text-xs text-red-800">
                            <b>{v.type}:</b> {v.reason}
                            {v.ayurvedicText && <span className="block text-[10px] text-red-600 italic mt-0.5">Citation: {v.ayurvedicText}</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═════════════════════════════════════════════════════════════════ */}
        {/* TAB 2: AYURVEDIC VIRUDDHA AHAAR SANDBOX */}
        {/* ═════════════════════════════════════════════════════════════════ */}
        {activeTab === 'viruddha' && (
          <div className="space-y-8">
            {/* Header banner */}
            <div className="bg-gradient-to-r from-emerald-800 to-teal-900 text-white p-6 rounded-3xl shadow-sm">
              <span className="text-xs font-semibold tracking-wider uppercase text-emerald-300">Precision Ayurveda Engine</span>
              <h2 className="text-2xl font-bold font-display mt-1">Viruddha Ahaar (Food Incompatibility) Lab</h2>
              <p className="text-xs text-emerald-100 max-w-2xl mt-2">
                In classical Ayurveda (Charaka Samhita 26.81-105 & Ashtanga Hridayam), certain food combinations upset the bodily doshas (Vata, Pitta, Kapha) and form toxic metabolites (ama). Test any combination below.
              </p>
            </div>

            {/* Sandbox Container */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Left Column: Preset Tests & Custom Add */}
              <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-6">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 font-display mb-2">1. Test Classical Combinations</h3>
                  <div className="grid grid-cols-1 gap-2">
                    {[
                      { label: '🥛 Milk + 🍋 Lemon / Citrus', items: ['milk', 'lemon'] },
                      { label: '🍯 Honey + 🧈 Ghee (Equal ratio)', items: ['honey', 'ghee'] },
                      { label: '🐟 Fish + 🥛 Milk', items: ['fish', 'milk'] },
                      { label: '🐟 Fish + 🥣 Curd / Yogurt', items: ['fish', 'curd'] },
                      { label: '🥛 Milk + 🍌 Banana', items: ['milk', 'banana'] },
                      { label: '🍛 Spinach + 🧀 Paneer (Safe)', items: ['spinach', 'paneer'] }
                    ].map((preset, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          setViruddhaSelected(preset.items);
                          handleCheckViruddha(preset.items);
                        }}
                        className="text-left text-xs font-medium p-2.5 rounded-xl border border-slate-200 hover:border-emerald-500 hover:bg-emerald-50 transition-all flex items-center justify-between"
                      >
                        <span>{preset.label}</span>
                        <span className="text-[10px] text-slate-400">Test →</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-bold text-slate-900 font-display mb-2">2. Add Custom Ingredient</h3>
                  <form onSubmit={handleAddCustomFood} className="flex gap-2">
                    <input
                      type="text"
                      placeholder="e.g. tamarind, milk, honey"
                      value={customFoodInput}
                      onChange={(e) => setCustomFoodInput(e.target.value)}
                      className="flex-1 text-xs border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-emerald-500"
                    />
                    <button type="submit" className="bg-emerald-600 text-white text-xs font-semibold px-4 py-2 rounded-xl hover:bg-emerald-700">
                      Add
                    </button>
                  </form>
                </div>
              </div>

              {/* Right Column: Active Combination & Analysis Result */}
              <div className="lg:col-span-2 bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-6">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold text-slate-900 font-display">Current Food Mixture Under Test</h3>
                    <button
                      onClick={() => handleCheckViruddha()}
                      className="text-xs bg-emerald-100 text-emerald-800 font-semibold px-3 py-1 rounded-lg hover:bg-emerald-200"
                    >
                      Re-Evaluate 🔄
                    </button>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 p-3 bg-slate-50 rounded-xl border border-dashed border-slate-200 min-h-[50px]">
                    {viruddhaSelected.map((item, idx) => (
                      <span key={idx} className="bg-white border border-slate-200 text-slate-800 font-medium px-3 py-1 rounded-lg text-xs shadow-sm flex items-center space-x-2">
                        <span className="capitalize">{item}</span>
                        <button onClick={() => handleRemoveViruddhaItem(item)} className="text-slate-400 hover:text-red-500 font-bold ml-1">×</button>
                      </span>
                    ))}
                    {viruddhaSelected.length === 0 && (
                      <span className="text-xs text-slate-400 italic">Select preset or add ingredients above to test...</span>
                    )}
                  </div>
                </div>

                {loadingViruddha ? (
                  <div className="py-12 text-center text-slate-400 text-xs">Evaluating classical Ayurvedic rules...</div>
                ) : viruddhaResult ? (
                  <div className="space-y-4">
                    {/* Score Bar */}
                    <div className={`p-4 rounded-2xl border flex items-center justify-between ${
                      viruddhaResult.isCompatible
                        ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                        : 'bg-red-50 border-red-200 text-red-900'
                    }`}>
                      <div>
                        <span className="text-xs font-bold uppercase tracking-wider block">
                          {viruddhaResult.isCompatible ? '✅ Safe Ayurvedic Combination' : `⚠️ ${viruddhaResult.overallSeverity} Severity Conflict Detected`}
                        </span>
                        <p className="text-xs mt-1 opacity-90">
                          {viruddhaResult.isCompatible
                            ? 'No biological clashes found. Ingredients possess harmonious veerya and vipaka.'
                            : 'This combination produces biological antagonism according to classical Ayurvedic pharmacology.'}
                        </p>
                      </div>
                      <div className="text-right">
                        <span className="text-2xl font-black font-display">{(viruddhaResult.compatibilityScore * 100).toFixed(0)}%</span>
                        <span className="block text-[10px] opacity-75">Compatibility</span>
                      </div>
                    </div>

                    {/* Violations List */}
                    {viruddhaResult.violations?.length > 0 && (
                      <div className="space-y-3">
                        <h4 className="text-xs font-bold uppercase text-slate-600">Contraindications Identified</h4>
                        {viruddhaResult.violations.map((v, i) => (
                          <div key={i} className="p-4 rounded-xl border border-red-200 bg-white shadow-sm space-y-1.5">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-red-700">{v.type}</span>
                              <span className="text-[10px] font-bold uppercase bg-red-100 text-red-800 px-2 py-0.5 rounded">
                                Severity: {v.severity}
                              </span>
                            </div>
                            <p className="text-xs text-slate-700">{v.reason}</p>
                            {v.ayurvedicText && (
                              <p className="text-[11px] text-amber-800 italic bg-amber-50 px-2 py-1 rounded inline-block">
                                📜 Classical Text Reference: {v.ayurvedicText}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Recommendations */}
                    {viruddhaResult.recommendations?.length > 0 && (
                      <div className="bg-emerald-50/70 p-4 rounded-xl border border-emerald-200">
                        <h4 className="text-xs font-bold text-emerald-900 mb-1">🌿 Safe Ayurvedic Alternatives & Remedies</h4>
                        <ul className="text-xs text-emerald-800 space-y-1 list-disc list-inside">
                          {viruddhaResult.recommendations.map((rec, i) => (
                            <li key={i}>{rec}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        )}

        {/* ═════════════════════════════════════════════════════════════════ */}
        {/* TAB 3: SMART PANTRY & EXPIRY TRACKER */}
        {/* ═════════════════════════════════════════════════════════════════ */}
        {activeTab === 'pantry' && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-2xl shadow-sm border border-slate-200">
              <div>
                <h2 className="text-lg font-bold text-slate-900 font-display">Pantry Inventory & Expiry Management</h2>
                <p className="text-xs text-slate-500">
                  Items expiring soon are given dynamic boosting in the GNN ranking model to minimize household food waste.
                </p>
              </div>
              <div className="flex items-center space-x-3 text-xs">
                <span className="flex items-center space-x-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500"></span>
                  <span className="text-slate-600">Urgent (≤2d)</span>
                </span>
                <span className="flex items-center space-x-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                  <span className="text-slate-600">Warning (≤5d)</span>
                </span>
                <span className="flex items-center space-x-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                  <span className="text-slate-600">Fresh (6d+)</span>
                </span>
              </div>
            </div>

            {/* Add Pantry Form */}
            <form onSubmit={handleAddPantryItem} className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 grid grid-cols-1 sm:grid-cols-5 gap-3 items-end">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Ingredient Name</label>
                <input
                  type="text"
                  placeholder="e.g. Tomato, Spinach, Toor Dal"
                  value={newPantryItem.name}
                  onChange={(e) => setNewPantryItem({ ...newPantryItem, name: e.target.value })}
                  className="w-full text-xs border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-emerald-500"
                  required
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Quantity & Unit</label>
                <div className="flex gap-1">
                  <input
                    type="number"
                    value={newPantryItem.quantity}
                    onChange={(e) => setNewPantryItem({ ...newPantryItem, quantity: Number(e.target.value) })}
                    className="w-2/3 text-xs border border-slate-200 rounded-xl px-2 py-2 focus:outline-none focus:border-emerald-500"
                    required
                  />
                  <select
                    value={newPantryItem.unit}
                    onChange={(e) => setNewPantryItem({ ...newPantryItem, unit: e.target.value })}
                    className="w-1/3 text-xs border border-slate-200 rounded-xl px-1 py-2 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="g">g</option>
                    <option value="ml">ml</option>
                    <option value="kg">kg</option>
                    <option value="piece">pcs</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Days Until Expiry</label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  value={newPantryItem.daysUntilExpiry}
                  onChange={(e) => setNewPantryItem({ ...newPantryItem, daysUntilExpiry: Number(e.target.value) })}
                  className="w-full text-xs border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Category</label>
                <select
                  value={newPantryItem.category}
                  onChange={(e) => setNewPantryItem({ ...newPantryItem, category: e.target.value })}
                  className="w-full text-xs border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-emerald-500"
                >
                  <option value="Vegetables">Vegetables</option>
                  <option value="Dairy">Dairy</option>
                  <option value="Pulses">Pulses</option>
                  <option value="Cereals">Cereals</option>
                  <option value="Spices">Spices</option>
                  <option value="Leafy Vegetables">Leafy Vegetables</option>
                </select>
              </div>
              <button
                type="submit"
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs py-2.5 rounded-xl shadow-sm transition-all"
              >
                + Add Ingredient
              </button>
            </form>

            {/* Pantry Grid */}
            {loadingPantry ? (
              <div className="py-16 text-center text-slate-400">Loading pantry items...</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {pantryItems.map((item) => {
                  const isUrgent = item.daysUntilExpiry <= 2;
                  const isWarning = item.daysUntilExpiry > 2 && item.daysUntilExpiry <= 5;

                  return (
                    <div
                      key={item.itemId}
                      className={`p-4 rounded-2xl bg-white border transition-all shadow-sm flex flex-col justify-between ${
                        isUrgent
                          ? 'border-red-300 ring-1 ring-red-200'
                          : isWarning
                          ? 'border-amber-300'
                          : 'border-slate-200'
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[10px] uppercase font-bold text-slate-400">{item.category}</span>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            isUrgent ? 'bg-red-100 text-red-800' : isWarning ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
                          }`}>
                            {item.daysUntilExpiry === 1 ? '1 day left' : `${item.daysUntilExpiry} days left`}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-slate-900 font-display">{item.name}</h4>
                        <p className="text-xs text-slate-500 mt-0.5">{item.quantity} {item.unit}</p>
                      </div>

                      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                        <span className="text-[10px] text-slate-400">ID: {item.itemId.slice(-6)}</span>
                        <button
                          onClick={() => handleDeletePantryItem(item.itemId, item.name)}
                          className="text-xs text-red-500 hover:text-red-700 font-semibold"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ═════════════════════════════════════════════════════════════════ */}
        {/* TAB 4: 7-DAY MEAL PLANNER */}
        {/* ═════════════════════════════════════════════════════════════════ */}
        {activeTab === 'meal_plan' && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-2xl shadow-sm border border-slate-200">
              <div>
                <h2 className="text-lg font-bold text-slate-900 font-display">Personalized 7-Day Meal Schedule</h2>
                <p className="text-xs text-slate-500">
                  Calculated against your profile macro targets with complete Ayurvedic safety verification across all 4 daily meals.
                </p>
              </div>
              <button
                onClick={fetchMealPlan}
                className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-xl shadow-sm"
              >
                Regenerate Plan 🔄
              </button>
            </div>

            {loadingPlan ? (
              <div className="py-20 text-center text-slate-400">Generating balanced 7-day plan...</div>
            ) : mealPlan?.plan ? (
              <div className="space-y-6">
                {/* Day selector pills */}
                <div className="flex space-x-2 overflow-x-auto pb-2">
                  {mealPlan.plan.map((d) => (
                    <button
                      key={d.day}
                      onClick={() => setSelectedPlanDay(d.day)}
                      className={`px-4 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                        selectedPlanDay === d.day
                          ? 'bg-emerald-600 text-white shadow-sm'
                          : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      {d.dayLabel}
                    </button>
                  ))}
                </div>

                {/* Selected Day View */}
                {(() => {
                  const currentDayData = mealPlan.plan.find(d => d.day === selectedPlanDay) || mealPlan.plan[0];
                  return (
                    <div className="space-y-6">
                      {/* Daily Macro Summary Banner */}
                      <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
                        <div>
                          <span className="text-lg font-bold text-slate-900 font-display">{currentDayData.dailyNutrition.calories}</span>
                          <span className="block text-[10px] text-slate-500">Calories (kcal)</span>
                        </div>
                        <div>
                          <span className="text-lg font-bold text-emerald-600 font-display">{currentDayData.dailyNutrition.proteinG}g</span>
                          <span className="block text-[10px] text-slate-500">Protein</span>
                        </div>
                        <div>
                          <span className="text-lg font-bold text-blue-600 font-display">{currentDayData.dailyNutrition.carbsG}g</span>
                          <span className="block text-[10px] text-slate-500">Carbohydrates</span>
                        </div>
                        <div>
                          <span className="text-lg font-bold text-amber-600 font-display">{currentDayData.dailyNutrition.fatG}g</span>
                          <span className="block text-[10px] text-slate-500">Fats</span>
                        </div>
                        <div>
                          <span className="text-lg font-bold text-teal-600 font-display">{currentDayData.dailyNutrition.fibreG}g</span>
                          <span className="block text-[10px] text-slate-500">Dietary Fibre</span>
                        </div>
                      </div>

                      {/* 4 Meals Grid */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {[
                          { slot: 'Breakfast', icon: '🌅', meal: currentDayData.meals.breakfast },
                          { slot: 'Lunch', icon: '☀️', meal: currentDayData.meals.lunch },
                          { slot: 'Afternoon Snack', icon: '🍵', meal: currentDayData.meals.snack },
                          { slot: 'Dinner', icon: '🌙', meal: currentDayData.meals.dinner }
                        ].map((m, idx) => (
                          <div key={idx} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
                            <div>
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-bold text-emerald-700 flex items-center space-x-1">
                                  <span>{m.icon}</span>
                                  <span>{m.slot}</span>
                                </span>
                                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                                  {m.meal.cuisine} • {m.meal.dietType}
                                </span>
                              </div>
                              <h4 className="text-base font-bold text-slate-900 font-display">{m.meal.title}</h4>
                              <p className="text-xs text-slate-600 mt-1 italic">{m.meal.highlights}</p>

                              {/* Ingredients summary */}
                              <div className="mt-3 flex flex-wrap gap-1">
                                {m.meal.ingredients?.map((ing, i) => (
                                  <span key={i} className="text-[10px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                                    {ing.name} ({ing.quantity}{ing.unit})
                                  </span>
                                ))}
                              </div>
                            </div>

                            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 font-medium">
                              <span>🔥 {m.meal.calories} kcal</span>
                              <span>🥩 {m.meal.proteinG}g P</span>
                              <span>🌾 {m.meal.carbsG}g C</span>
                              <span>🥑 {m.meal.fatG}g F</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}
              </div>
            ) : null}
          </div>
        )}

        {/* ═════════════════════════════════════════════════════════════════ */}
        {/* TAB 5: AI VISION & SUPERMARKET BILL SCANNER */}
        {/* ═════════════════════════════════════════════════════════════════ */}
        {activeTab === 'vision' && (
          <div className="space-y-6">
            <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900 font-display">AI Vision & Supermarket Bill Scanner</h2>
                <p className="text-xs text-slate-500 mt-1">
                  Scan printed paper receipts or digital grocery lists from any store (DMart, Reliance Fresh, BigBasket, Blinkit, Zepto, More, Kirana), or photograph raw food on your counter.
                </p>
              </div>

              {/* Scan Mode Toggle */}
              <div className="flex bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-semibold">
                <button
                  onClick={() => setScanMode('receipt')}
                  className={`px-3 py-1.5 rounded-lg transition-all ${
                    scanMode === 'receipt' ? 'bg-white text-emerald-800 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  🧾 Supermarket Bill / Receipt
                </button>
                <button
                  onClick={() => setScanMode('food_photo')}
                  className={`px-3 py-1.5 rounded-lg transition-all ${
                    scanMode === 'food_photo' ? 'bg-white text-emerald-800 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  📸 Fresh Food Photo
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Scan Trigger Box */}
              <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-5">
                {scanMode === 'receipt' ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-slate-900 font-display">Scan or Paste Any Supermarket Receipt</h3>
                      <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded">
                        Auto Non-Food Filter
                      </span>
                    </div>

                    <div className="border-2 border-dashed border-slate-200 rounded-2xl p-6 text-center bg-slate-50 space-y-3">
                      <span className="text-3xl">🧾</span>
                      <p className="text-xs font-semibold text-slate-700">Upload Receipt Image or Test Sample Bill</p>
                      
                      <div className="flex flex-wrap gap-2 justify-center pt-1">
                        <label className="cursor-pointer bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-xl shadow-sm transition-all inline-block">
                          Upload Receipt Photo
                          <input type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />
                        </label>
                        <button
                          onClick={() => handleScanReceipt()}
                          disabled={loadingVision}
                          className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-4 py-2 rounded-xl shadow-sm transition-all"
                        >
                          Test DMart / Store Bill Demo
                        </button>
                      </div>
                    </div>

                    {/* Direct Text Paste Box */}
                    <div className="space-y-2">
                      <label className="block text-[11px] font-semibold text-slate-600">
                        Or Paste Receipt Lines (from Blinkit / BigBasket / Instamart SMS / Invoice):
                      </label>
                      <textarea
                        rows={4}
                        placeholder={"DMART INVOICE\nAashirvaad Atta 5kg\nSurf Excel Detergent 1kg\nTata Sampann Toor Dal 1kg\nAmul Taaza Milk 500ml\nVim Dishwash Bar\nFortune Sunflower Oil 1L\nCarry Bag"}
                        value={receiptTextInput}
                        onChange={(e) => setReceiptTextInput(e.target.value)}
                        className="w-full text-xs font-mono border border-slate-200 rounded-xl p-3 focus:outline-none focus:border-emerald-500"
                      />
                      <button
                        onClick={() => handleScanReceipt(receiptTextInput)}
                        disabled={loadingVision || !receiptTextInput.trim()}
                        className="w-full bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold py-2 rounded-xl transition-all disabled:opacity-50"
                      >
                        Parse Pasted Receipt Lines 🔍
                      </button>
                    </div>

                    <div className="text-[11px] text-slate-500 bg-emerald-50/60 p-3 rounded-xl border border-emerald-100">
                      🛡️ <b>Smart Privacy & Food Focus:</b> Non-food items (soaps, detergents, carry bags, toiletries) are automatically ignored and discarded! Only nutritious foods are added to your pantry.
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-slate-900 font-display">Scan Fresh Food & Grocery Photo</h3>
                    <div className="border-2 border-dashed border-slate-200 rounded-2xl p-8 text-center bg-slate-50 flex flex-col items-center justify-center space-y-3">
                      <span className="text-4xl">📸</span>
                      <div>
                        <p className="text-xs font-semibold text-slate-700">Take Photo of Food on Table / Kitchen</p>
                        <p className="text-[10px] text-slate-400 mt-0.5">Upload a live photo or test preset scenes</p>
                      </div>
                      
                      <div className="flex flex-wrap gap-2 justify-center pt-2">
                        <label className="cursor-pointer bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-xl shadow-sm transition-all inline-block">
                          Upload Food Image
                          <input type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />
                        </label>
                        <button
                          onClick={() => handleSimulateScan('greens')}
                          disabled={loadingVision}
                          className="bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold px-3 py-2 rounded-xl shadow-sm transition-all"
                        >
                          Preset: Spinach & Paneer
                        </button>
                        <button
                          onClick={() => handleSimulateScan('pulses')}
                          disabled={loadingVision}
                          className="bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold px-3 py-2 rounded-xl shadow-sm transition-all"
                        >
                          Preset: Chickpeas & Potatoes
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Scan Results */}
              <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 font-display">Pantry Items Extracted</h3>
                    <p className="text-[11px] text-slate-400">Edible groceries normalized to ICMR IFCT 2017</p>
                  </div>
                  {visionResults && visionResults.detectedItems?.length > 0 && (
                    <button
                      onClick={handleImportVisionToPantry}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-3.5 py-1.5 rounded-lg shadow-sm"
                    >
                      + Import All to Pantry
                    </button>
                  )}
                </div>

                {loadingVision ? (
                  <div className="py-16 text-center text-slate-400 text-xs">Analyzing and filtering items...</div>
                ) : visionResults ? (
                  <div className="space-y-4">
                    <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 flex items-center justify-between text-xs text-emerald-900">
                      <span>Engine: <b>{visionResults.processingMethod}</b></span>
                      <span>Total: <b>{visionResults.totalEstimatedCalories} kcal</b></span>
                    </div>

                    <div className="space-y-2 max-h-[350px] overflow-y-auto pr-1">
                      {visionResults.detectedItems?.map((item, idx) => (
                        <div key={idx} className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between text-xs">
                          <div>
                            <div className="flex items-center space-x-2">
                              <span className="font-bold text-slate-900">{item.name}</span>
                              <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded">
                                {item.category || 'Pantry'}
                              </span>
                            </div>
                            <span className="block text-[10px] text-slate-500 mt-0.5">
                              Quantity: <b>{item.estimatedQuantity} {item.unit}</b> • Expiry: <b>{item.daysUntilExpiry || 30} days</b> • IFCT: {item.ifctCode || 'N/A'}
                            </span>
                          </div>
                          <div className="text-right">
                            <span className="font-semibold text-emerald-700">{item.estimatedCalories} kcal</span>
                            <span className="block text-[10px] text-slate-400">{(item.confidence * 100).toFixed(0)}% match</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="py-16 text-center text-slate-400 text-xs italic">
                    No receipt or image scanned yet. Click "Test DMart / Store Bill Demo" or paste receipt text above!
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'profile' && (
          <section className="max-w-5xl mx-auto space-y-5">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-[10px] uppercase font-bold tracking-wide text-emerald-700">Account profile</p>
                <h2 className="text-xl font-bold text-slate-900 mt-1">Nutrition and recommendation profile</h2>
              </div>
              <span className="text-xs text-slate-500">Signed in as {authUser?.email}</span>
            </div>

            {!profileDraft ? (
              <div className="bg-white border border-slate-200 rounded-xl p-8 text-sm text-slate-500">Loading profile...</div>
            ) : (
              <form onSubmit={handleSaveProfile} className="bg-white border border-slate-200 rounded-xl shadow-sm divide-y divide-slate-100">
                <div className="p-5 grid sm:grid-cols-2 gap-4">
                  <label className="text-xs font-medium text-slate-600">First name
                    <input value={profileDraft.firstName} onChange={event => setProfileDraft({ ...profileDraft, firstName: event.target.value })} required maxLength={60} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
                  </label>
                  <label className="text-xs font-medium text-slate-600">Last name
                    <input value={profileDraft.lastName} onChange={event => setProfileDraft({ ...profileDraft, lastName: event.target.value })} required maxLength={60} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
                  </label>
                </div>

                <div className="p-5">
                  <h3 className="text-sm font-bold text-slate-900">Personal details</h3>
                  <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
                    <label className="text-xs font-medium text-slate-600">Age
                      <input type="number" min="13" max="120" value={profileDraft.profile.age} onChange={event => updateProfileField('age', event.target.value)} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
                    </label>
                    <label className="text-xs font-medium text-slate-600">Gender
                      <select value={profileDraft.profile.gender} onChange={event => updateProfileField('gender', event.target.value)} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm bg-white">
                        <option value="">Prefer not to say</option><option>Female</option><option>Male</option><option>Non-binary</option>
                      </select>
                    </label>
                    <label className="text-xs font-medium text-slate-600">Height (cm)
                      <input type="number" min="80" max="250" value={profileDraft.profile.heightCm} onChange={event => updateProfileField('heightCm', event.target.value)} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
                    </label>
                    <label className="text-xs font-medium text-slate-600">Weight (kg)
                      <input type="number" min="25" max="400" step="0.1" value={profileDraft.profile.weightKg} onChange={event => updateProfileField('weightKg', event.target.value)} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
                    </label>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-4 mt-4">
                    <label className="text-xs font-medium text-slate-600">Activity level
                      <select value={profileDraft.profile.activityLevel} onChange={event => updateProfileField('activityLevel', event.target.value)} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm bg-white">
                        {['Sedentary', 'Light', 'Moderate', 'Active', 'Very Active'].map(value => <option key={value}>{value}</option>)}
                      </select>
                    </label>
                    <label className="text-xs font-medium text-slate-600">Diet type
                      <select value={profileDraft.profile.dietType} onChange={event => updateProfileField('dietType', event.target.value)} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm bg-white">
                        {['Vegetarian', 'Vegan', 'Eggetarian', 'Non-Vegetarian', 'Any'].map(value => <option key={value}>{value}</option>)}
                      </select>
                    </label>
                  </div>
                </div>

                <div className="p-5 grid lg:grid-cols-2 gap-6">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Allergies</h3>
                    <label className="block text-xs text-slate-600 mt-3">Comma-separated ingredients to exclude
                      <input value={profileDraft.profile.allergiesText} onChange={event => updateProfileField('allergiesText', event.target.value)} placeholder="Peanuts, shellfish, dairy" className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
                    </label>
                  </div>
                  <fieldset>
                    <legend className="text-sm font-bold text-slate-900">Health conditions</legend>
                    <div className="grid grid-cols-2 gap-2 mt-3">
                      {[
                        ['HC_ANEMIA', 'Anemia'], ['HC_DIABETES', 'Diabetes'],
                        ['HC_CARDIAC', 'Heart health'], ['HC_OBESITY', 'Weight management'],
                        ['HC_BONE', 'Bone health'], ['HC_DIGESTION', 'Digestion'],
                        ['HC_IMMUNITY', 'Immunity']
                      ].map(([value, label]) => (
                        <label key={value} className="flex items-center gap-2 text-xs text-slate-700">
                          <input type="checkbox" checked={profileDraft.profile.healthConditions.includes(value)} onChange={() => toggleProfileArrayValue('healthConditions', value)} className="accent-emerald-700" />
                          {label}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                </div>

                <div className="p-5">
                  <fieldset>
                    <legend className="text-sm font-bold text-slate-900">Preferred cuisines</legend>
                    <div className="flex flex-wrap gap-x-5 gap-y-3 mt-3">
                      {['Pan-Indian', 'Punjabi', 'Maharashtrian', 'South Indian', 'Gujarati'].map(value => (
                        <label key={value} className="flex items-center gap-2 text-xs text-slate-700">
                          <input type="checkbox" checked={profileDraft.profile.preferredCuisines.includes(value)} onChange={() => toggleProfileArrayValue('preferredCuisines', value)} className="accent-emerald-700" />
                          {value}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                </div>

                <div className="p-5">
                  <h3 className="text-sm font-bold text-slate-900">Daily nutrition targets</h3>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
                    {[
                      ['calories', 'Calories', 'kcal'], ['protein', 'Protein', 'g'],
                      ['carbs', 'Carbohydrates', 'g'], ['fat', 'Fat', 'g']
                    ].map(([key, label, unit]) => (
                      <label key={key} className="text-xs font-medium text-slate-600">{label} ({unit})
                        <input type="number" min="0" value={profileDraft.profile.macroTargets[key]} onChange={event => setProfileDraft(previous => ({
                          ...previous,
                          profile: {
                            ...previous.profile,
                            macroTargets: { ...previous.profile.macroTargets, [key]: event.target.value }
                          }
                        }))} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm" />
                      </label>
                    ))}
                  </div>
                </div>

                <div className="p-5 flex flex-wrap items-center justify-between gap-4">
                  <div className="flex flex-wrap items-center gap-5">
                    <label className="flex items-center gap-2 text-xs text-slate-700">
                      <input type="checkbox" checked={profileDraft.profile.applyAyurvedicConstraints} onChange={event => updateProfileField('applyAyurvedicConstraints', event.target.checked)} className="accent-emerald-700" />
                      Apply Ayurvedic food constraints
                    </label>
                    <label className="text-xs text-slate-600">Conflict handling
                      <select value={profileDraft.profile.viruddhaStrictMode} onChange={event => updateProfileField('viruddhaStrictMode', event.target.value)} className="ml-2 border border-slate-300 rounded-lg px-2 py-2 bg-white">
                        <option value="FILTER">Filter</option><option value="WARN">Warn</option><option value="OFF">Off</option>
                      </select>
                    </label>
                  </div>
                  <div className="flex items-center gap-3">
                    {profileError && <p role="alert" className="text-xs text-red-700">{profileError}</p>}
                    <button type="submit" disabled={savingProfile} className="px-4 py-2.5 rounded-lg bg-emerald-700 text-white text-xs font-semibold hover:bg-emerald-800 disabled:opacity-50">
                      {savingProfile ? 'Saving...' : 'Save profile'}
                    </button>
                  </div>
                </div>
              </form>
            )}
          </section>
        )}

        {/* ═════════════════════════════════════════════════════════════════ */}
        {/* TAB 6: RAG FOOD COACH AI CHATBOT */}
        {/* ═════════════════════════════════════════════════════════════════ */}
        {activeTab === 'chatbot' && (
          <div className="max-w-4xl mx-auto bg-white rounded-3xl shadow-sm border border-slate-200 overflow-hidden flex flex-col h-[650px]">
            {/* Chat Header */}
            <div className="p-4 bg-emerald-800 text-white flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-lg bg-emerald-700 flex items-center justify-center text-lg">🤖</div>
                <div>
                  <h3 className="text-sm font-bold font-display">FoodCoach AI Knowledge Assistant</h3>
                  <p className="text-[10px] text-emerald-200">Conversational food coaching with nutrition knowledge grounding</p>
                </div>
              </div>
            </div>

            {/* Chat Body */}
            <div className="flex-1 p-5 overflow-y-auto space-y-4 bg-slate-50/50">
              {chatMessages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] rounded-2xl p-4 text-xs space-y-2 ${
                    msg.role === 'user'
                      ? 'bg-emerald-600 text-white rounded-br-none shadow-sm'
                      : 'bg-white text-slate-800 border border-slate-200 rounded-bl-none shadow-sm'
                  }`}>
                    <p className="leading-relaxed whitespace-pre-line">{msg.content}</p>

                    {msg.role === 'assistant' && msg.content && (
                      <div className="pt-1 flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleSpeakReply(msg.content, msg.language)}
                          title="Play this reply aloud"
                          aria-label="Play this reply aloud"
                          className="text-[10px] text-emerald-700 hover:text-emerald-900 font-semibold"
                        >
                          {playingMessage === msg.content ? '◼ Stop audio' : '🔊 Listen'}
                        </button>
                        {msg.provider === 'rag_fallback' && (
                          <span className="text-[10px] text-amber-700">Local language model unavailable; showing retrieved facts.</span>
                        )}
                      </div>
                    )}

                    {/* Citations / Sources */}
                    {msg.sources?.length > 0 && (
                      <div className="pt-2 border-t border-slate-100 flex flex-wrap gap-1">
                        <span className="text-[10px] font-semibold text-slate-400">Sources:</span>
                        {msg.sources.map((s, i) => (
                          <span key={i} className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                            📜 {s}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Suggestions */}
                    {msg.suggestions?.length > 0 && (
                      <div className="pt-2 flex flex-wrap gap-1.5">
                        {msg.suggestions.map((sug, i) => (
                          <button
                            key={i}
                            onClick={() => handleSendChat(sug)}
                            className="text-[10px] bg-emerald-50 text-emerald-800 font-medium px-2.5 py-1 rounded-full border border-emerald-200 hover:bg-emerald-100 transition-all text-left"
                          >
                            💡 {sug}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {loadingChat && (
                <div className="text-xs text-slate-400 italic">FoodCoach AI is analyzing nutritional literature...</div>
              )}
            </div>

            {/* Chat Input Bar */}
            <div className="p-3 bg-white border-t border-slate-200 space-y-2">
              {chatError && <p role="alert" className="text-[11px] text-red-700">{chatError}</p>}
              {(loadingVoice || loadingChat) && (
                <p className="text-[10px] text-slate-500">
                  {loadingVoice ? 'Transcribing your recording...' : 'FoodCoach is preparing a reply...'}
                </p>
              )}
              <div className="flex gap-2 items-center">
                <select
                  aria-label="Reply language"
                  value={chatLanguage}
                  onChange={e => setChatLanguage(e.target.value)}
                  className="w-28 shrink-0 text-xs border border-slate-200 rounded-xl px-2 py-3 bg-white"
                >
                  <option value="auto">Auto</option>
                  <option value="en">English</option>
                  <option value="hi">Hindi</option>
                  <option value="mr">Marathi</option>
                </select>
                <button
                  type="button"
                  onClick={handleToggleVoiceInput}
                  disabled={loadingVoice || loadingChat}
                  title={recordingVoice ? 'Stop recording' : 'Record a voice question'}
                  aria-label={recordingVoice ? 'Stop recording' : 'Record a voice question'}
                  className={`shrink-0 text-xs font-semibold px-3 py-3 rounded-xl border transition-colors disabled:opacity-50 ${recordingVoice ? 'bg-red-50 text-red-700 border-red-200' : 'bg-white text-emerald-800 border-slate-200 hover:bg-emerald-50'}`}
                >
                  {recordingVoice ? '■ Stop' : '🎙 Speak'}
                </button>
              <input
                type="text"
                placeholder="Ask in English, Hindi, or Marathi..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendChat()}
                className="flex-1 text-xs border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:border-emerald-500"
              />
              <button
                onClick={() => handleSendChat()}
                disabled={loadingChat || loadingVoice}
                className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-5 py-3 rounded-xl shadow-sm transition-all"
              >
                Send
              </button>
              </div>
            </div>
          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-500">
        FoodCoach AI (Final Year Project) — Real Full-Stack Implementation: React 18, Node.js Gateway, FastAPI ML, Neo4j Graph DB, and ICMR-NIN IFCT 2017 Dataset.
      </footer>
    </div>
  );
}
