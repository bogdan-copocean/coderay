/**
 * App config.
 */

const API_URL = process.env.API_URL || 'http://localhost:3000';
const ENV = process.env.NODE_ENV || 'development';

export default {
    apiUrl: API_URL,
    env: ENV,
};
