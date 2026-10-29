const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { randomUUID } = require('crypto');
const User = require('../models/User');
const authenticate = require('../middleware/authenticate');

const router = express.Router();
const ACCESS_SECRET = () => process.env.JWT_ACCESS_SECRET || 'foodcoach-local-access-secret-change-before-deploy';
const REFRESH_SECRET = () => process.env.JWT_REFRESH_SECRET || 'foodcoach-local-refresh-secret-change-before-deploy';
const accessCookie = () => ({
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 15 * 60 * 1000
});
const refreshCookie = () => ({
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/api/auth',
    maxAge: 7 * 24 * 60 * 60 * 1000
});

function safeUser(user) {
    return {
        userId: user.userId,
        name: user.name,
        firstName: user.firstName,
        lastName: user.lastName,
        email: user.email,
        profilePicUrl: user.profilePicUrl,
        role: user.role,
        profile: user.profile,
        progress: user.progress,
        weeklyGoals: user.weeklyGoals
    };
}

async function setSession(user, res) {
    const subject = user._id.toString();
    const accessToken = jwt.sign({ sub: subject, userId: user.userId, sessionVersion: user.sessionVersion }, ACCESS_SECRET(), { expiresIn: '15m' });
    const refreshToken = jwt.sign({ sub: subject, jti: randomUUID() }, REFRESH_SECRET(), { expiresIn: '7d' });
    user.refreshTokenHash = await bcrypt.hash(refreshToken, 12);
    await user.save();
    res.cookie('accessToken', accessToken, accessCookie());
    res.cookie('refreshToken', refreshToken, refreshCookie());
    return safeUser(user);
}

router.post('/register', async (req, res) => {
    const firstName = String(req.body.firstName || '').trim();
    const lastName = String(req.body.lastName || '').trim();
    const email = String(req.body.email || '').trim().toLowerCase();
    const password = String(req.body.password || '');
    if (!firstName || !lastName || !/^\S+@\S+\.\S+$/.test(email)) {
        return res.status(400).json({ error: 'Enter your first name, last name, and a valid email address.' });
    }
    if (password.length < 8 || !/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/\d/.test(password) || !/[^A-Za-z0-9]/.test(password)) {
        return res.status(400).json({ error: 'Password must be at least 8 characters and include uppercase, lowercase, a number, and a symbol.' });
    }

    try {
        const user = new User({
            firstName,
            lastName,
            name: `${firstName} ${lastName}`,
            email,
            passwordHash: await bcrypt.hash(password, 12)
        });
        await user.save();
        return res.status(201).json({ user: await setSession(user, res) });
    } catch (error) {
        if (error.code === 11000) return res.status(409).json({ error: 'An account with this email already exists.' });
        if (error.name === 'ValidationError') return res.status(400).json({ error: 'Please check the account details and try again.' });
        return res.status(500).json({ error: 'Could not create the account.' });
    }
});

router.post('/login', async (req, res) => {
    const email = String(req.body.email || '').trim().toLowerCase();
    const password = String(req.body.password || '');
    try {
        const user = await User.findOne({ email }).select('+passwordHash');
        if (!user || !(await bcrypt.compare(password, user.passwordHash))) {
            return res.status(401).json({ error: 'Email or password is incorrect.' });
        }
        user.lastLogin = new Date();
        return res.json({ user: await setSession(user, res) });
    } catch (error) {
        return res.status(500).json({ error: 'Could not sign in.' });
    }
});

router.post('/refresh', async (req, res) => {
    const refreshToken = req.cookies?.refreshToken;
    if (!refreshToken) return res.status(401).json({ error: 'Session expired. Please sign in again.' });
    try {
        const payload = jwt.verify(refreshToken, REFRESH_SECRET());
        const user = await User.findById(payload.sub).select('+refreshTokenHash');
        if (!user?.refreshTokenHash || !(await bcrypt.compare(refreshToken, user.refreshTokenHash))) {
            return res.status(401).json({ error: 'Session expired. Please sign in again.' });
        }
        return res.json({ user: await setSession(user, res) });
    } catch (error) {
        return res.status(401).json({ error: 'Session expired. Please sign in again.' });
    }
});

router.get('/me', authenticate, (req, res) => res.json({ user: safeUser(req.user) }));

router.post('/logout', authenticate, async (req, res) => {
    try {
        req.user.sessionVersion += 1;
        req.user.refreshTokenHash = null;
        await req.user.save();
        res.clearCookie('accessToken', { ...accessCookie(), maxAge: undefined });
        res.clearCookie('refreshToken', { ...refreshCookie(), maxAge: undefined });
        return res.json({ status: 'success' });
    } catch (error) {
        return res.status(500).json({ error: 'Could not sign out.' });
    }
});

module.exports = { router, safeUser };