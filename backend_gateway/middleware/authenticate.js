const jwt = require('jsonwebtoken');
const User = require('../models/User');

const authenticate = async (req, res, next) => {
    const bearerToken = req.get('authorization')?.replace(/^Bearer\s+/i, '');
    const token = req.cookies?.accessToken || bearerToken;
    if (!token) return res.status(401).json({ error: 'Authentication required.' });

    try {
        const payload = jwt.verify(token, process.env.JWT_ACCESS_SECRET || 'foodcoach-local-access-secret-change-before-deploy');
        const user = await User.findById(payload.sub);
        if (!user || payload.sessionVersion !== user.sessionVersion) {
            return res.status(401).json({ error: 'Authentication required.' });
        }
        req.user = user;
        return next();
    } catch (error) {
        return res.status(401).json({ error: 'Session expired. Please sign in again.' });
    }
};

module.exports = authenticate;