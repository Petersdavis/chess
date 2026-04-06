import React, { useState } from 'react';
import { auth, db } from './firebase.js';
import { createUserWithEmailAndPassword, signInWithEmailAndPassword, sendEmailVerification } from 'firebase/auth';
import { doc, setDoc } from 'firebase/firestore';
import { motion } from 'framer-motion';
import { Mail, Lock, CheckCircle, ArrowRight } from 'lucide-react';
import './AuthPage.css';

const AuthPage = () => {
    const [isLogin, setIsLogin] = useState(false);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (isLogin) {
                await signInWithEmailAndPassword(auth, email, password);
            } else {
                const userCredential = await createUserWithEmailAndPassword(auth, email, password);
                const user = userCredential.user;
                
                // Send verification immediately
                await sendEmailVerification(user);

                // Initialize placeholder doc
                await setDoc(doc(db, "users", user.uid), {
                    uid: user.uid,
                    email,
                    onboardingComplete: false,
                    createdAt: new Date().toISOString()
                });
            }
            setSuccess(true);
        } catch (err) {
            setError(err.message.replace("Firebase: ", ""));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-wrapper">
            <div className="mesh-gradient" />
            
            <motion.div 
                initial={{ opacity: 0, scale: 0.95, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                className="auth-container"
            >
                <div className="auth-card">
                    <div className="auth-header">
                        <div className="logo-badge">🎯</div>
                        <h1>{isLogin ? 'Welcome Back' : 'Sniper Enlistment'}</h1>
                        <p className="auth-subtitle">
                            {isLogin ? 'Authorize your session' : 'Secure your operative access code'}
                        </p>
                    </div>

                    <form onSubmit={handleSubmit} className="auth-form">
                        <div className="input-group">
                            <label><Mail size={16} /> Operative Email</label>
                            <input 
                                type="email" 
                                placeholder="name@domain.com" 
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                            />
                        </div>

                        <div className="input-group">
                            <label><Lock size={16} /> Access Code</label>
                            <input 
                                type="password" 
                                placeholder="••••••••" 
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>

                        {error && <div className="auth-error">{error}</div>}

                        <button className="auth-btn" disabled={loading}>
                            {loading ? 'Processing...' : (isLogin ? 'Access OS' : 'Begin Enlistment')} <ArrowRight size={18} />
                        </button>
                    </form>

                    <div className="auth-footer">
                        <button onClick={() => setIsLogin(!isLogin)} className="toggle-btn">
                            {isLogin ? "Need an operative profile? Enlist here" : "Already a recruit? Sign in"}
                        </button>
                    </div>
                </div>
            </motion.div>
        </div>
    );
};

export default AuthPage;
