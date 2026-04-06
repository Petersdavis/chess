import React, { useState, useEffect, useMemo } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { onAuthStateChanged, signOut, sendEmailVerification } from 'firebase/auth';
import { doc, getDoc } from 'firebase/firestore';
import { auth, db } from './firebase.js';
import AuthPage from './AuthPage.jsx';
import { motion, AnimatePresence } from 'framer-motion';
import { LogOut, Target, Database, Activity, Mail, CheckCircle, RefreshCcw, ChevronLeft, ChevronRight, Play } from 'lucide-react';
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";

/**
 * Verification Guard: Blocks access until email is verified.
 */
const VerificationGuard = ({ user, children }) => {
    const [refreshing, setRefreshing] = useState(false);

    const handleRefresh = async () => {
        setRefreshing(true);
        await auth.currentUser.reload();
        window.location.reload();
    };

    const handleResend = async () => {
        await sendEmailVerification(auth.currentUser);
        alert("Intelligence link re-sent.");
    };

    if (user && !user.emailVerified) {
        return (
            <div className="auth-wrapper">
                <div className="mesh-gradient" />
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="auth-container">
                    <div className="auth-card">
                        <div className="auth-header">
                            <div className="logo-badge">📩</div>
                            <h1>Verify Your Intel</h1>
                            <p className="auth-subtitle">We've sent a secure link to {user.email}. Check your inbox to activate your operative status.</p>
                        </div>
                        <div className="auth-form" style={{ gap: '16px' }}>
                            <button onClick={handleRefresh} className="auth-btn">
                                <RefreshCcw size={18} className={refreshing ? 'spin' : ''} /> Check Status
                            </button>
                            <button onClick={handleResend} className="social-btn">Resend Verification</button>
                            <button onClick={() => signOut(auth)} className="logout-btn" style={{ justifyContent: 'center' }}>
                                <LogOut size={18} /> Sign Out
                            </button>
                        </div>
                    </div>
                </motion.div>
            </div>
        );
    }
    return children;
};

/**
 * Onboarding Guard: Collects extra info before allowing dashboard access.
 */
const OnboardingPage = ({ user, onComplete }) => {
    const [fullName, setFullName] = useState('');
    const [chessCom, setChessCom] = useState('');
    const [lichess, setLichess] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        onComplete({ 
            fullName, 
            platforms: { 
                chessCom: chessCom || null, 
                lichess: lichess || null 
            } 
        });
    };

    return (
        <div className="auth-wrapper">
            <div className="mesh-gradient" />
            <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="auth-container">
                <div className="auth-card" style={{ maxWidth: '480px' }}>
                    <div className="auth-header" style={{ textAlign: 'left' }}>
                        <h1>Tactical Onboarding</h1>
                        <p className="auth-subtitle">Coordinate your platform accounts to unlock targeting capabilities.</p>
                    </div>
                    <form className="auth-form" onSubmit={handleSubmit}>
                        <div className="input-group">
                            <label>Full Name</label>
                            <input 
                                type="text" 
                                placeholder="Peter Davis" 
                                value={fullName}
                                onChange={(e) => setFullName(e.target.value)}
                                required 
                            />
                        </div>
                        <div className="input-group">
                            <label>Chess.com Username (Optional)</label>
                            <input 
                                type="text" 
                                placeholder="pdavis" 
                                value={chessCom}
                                onChange={(e) => setChessCom(e.target.value)}
                            />
                        </div>
                        <div className="input-group">
                            <label>Lichess Username (Optional)</label>
                            <input 
                                type="text" 
                                placeholder="pdavis_sniper" 
                                value={lichess}
                                onChange={(e) => setLichess(e.target.value)}
                            />
                        </div>
                        <button type="submit" className="auth-btn">
                            Initialize Sniper OS <CheckCircle size={18} />
                        </button>
                    </form>
                </div>
            </motion.div>
        </div>
    );
};

/**
 * Tactical Viewer: Renders a chessboard from a PGN.
 */
const TacticalViewer = ({ game, onClose }) => {
    const chess = useMemo(() => {
        const c = new Chess();
        try {
            if (game.pgn) c.loadPgn(game.pgn);
            else if (game.fen) c.load(game.fen);
        } catch (e) { console.error("Tactical load failed", e); }
        return c;
    }, [game]);

    const isWhite = game.white?.toLowerCase() === game.operative_username?.toLowerCase();
    const opponent = isWhite ? game.black : game.white;

    return (
        <div className="tactical-viewer">
            <div className="viewer-header">
                <div className="engagement-label">Tactical Review</div>
                <button onClick={onClose} className="close-btn"><ChevronRight /> Close</button>
            </div>
            <div className="board-wrapper">
                <div className="opp-info">Opponent: {opponent}</div>
                <div className="board-container">
                    <Chessboard 
                        position={chess.fen()} 
                        boardOrientation={isWhite ? 'white' : 'black'}
                        customBoardStyle={{
                            borderRadius: '12px',
                            boxShadow: '0 5px 15px rgba(0, 0, 0, 0.5)'
                        }}
                    />
                </div>
                <div className="opp-info">Operative: {isWhite ? game.white : game.black}</div>
            </div>
            <div className="tactical-stats">
              <div className="stat-pill">Result: {game.result}</div>
              <div className="stat-pill">ID: {game.game_id}</div>
            </div>
        </div>
    );
};

function App() {
    const [user, setUser] = useState(null);
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [onboardingComplete, setOnboardingComplete] = useState(false);
    const [games, setGames] = useState([]);
    const [selectedGame, setSelectedGame] = useState(null);

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
            if (currentUser) {
                try {
                    await currentUser.reload();
                    const freshUser = auth.currentUser;
                    setUser(freshUser);
                    
                    if (freshUser && freshUser.emailVerified) {
                        const { doc, getDoc } = await import('firebase/firestore');
                        const docRef = doc(db, "users", freshUser.uid);
                        const docSnap = await getDoc(docRef);
                        if (docSnap.exists()) {
                            const data = docSnap.data();
                            setProfile(data);
                            setOnboardingComplete(data.onboardingComplete);
                            if (data.onboardingComplete && data.platforms?.chessCom) {
                                fetchGames(data.platforms.chessCom);
                            }
                        }
                    }
                } catch (err) {
                    console.log("Authority session invalid.");
                    setUser(null);
                }
            } else {
                setUser(null);
            }
            setLoading(false);
        });
        return () => unsubscribe();
    }, []);

    const fetchGames = async (chessUsername) => {
        const { collection, query, where, orderBy, limit, getDocs } = await import('firebase/firestore');
        const q_white = query(collection(db, "games"), where("white", "==", chessUsername.toLowerCase()), orderBy("end_time", "desc"), limit(20));
        const q_black = query(collection(db, "games"), where("black", "==", chessUsername.toLowerCase()), orderBy("end_time", "desc"), limit(20));

        try {
            const [whiteSnap, blackSnap] = await Promise.all([getDocs(q_white), getDocs(q_black)]);
            const allGames = [...whiteSnap.docs, ...blackSnap.docs]
                .map(d => ({ id: d.id, ...d.data(), operative_username: chessUsername }))
                .sort((a, b) => b.end_time - a.end_time);
            setGames(allGames.slice(0, 20));
        } catch (err) {
            console.error("Battle search failed:", err);
        }
    };

    const handleOnboardingComplete = async (formData) => {
        try {
            const { updateDoc, doc } = await import('firebase/firestore');
            const docRef = doc(db, "users", user.uid);
            await updateDoc(docRef, { ...formData, onboardingComplete: true, updatedAt: new Date().toISOString() });
            setOnboardingComplete(true);
            if (formData.platforms?.chessCom) fetchGames(formData.platforms.chessCom);
        } catch (err) { alert("Error: " + err.message); }
    };

    if (loading) return <div className="loading-screen"><div className="loader" /></div>;

    return (
        <BrowserRouter>
            <Routes>
                <Route path="/login" element={user ? <Navigate to="/" replace /> : <AuthPage />} />
                <Route path="/" element={
                    !user ? <Navigate to="/login" replace /> : (
                        <VerificationGuard user={user}>
                            {user && !onboardingComplete ? (
                                <OnboardingPage user={user} onComplete={handleOnboardingComplete} />
                            ) : (
                                    <div className="dashboard-container">
                                        <header className="dashboard-header">
                                            <div className="brand"><span className="logo-emoji">🎯</span><h1>Sniper OS</h1></div>
                                            <div className="user-nav">
                                                <span className="user-tag">{profile?.fullName}</span>
                                                <button onClick={() => signOut(auth)} className="logout-btn"><LogOut size={18} /> Exit</button>
                                            </div>
                                        </header>
                                        
                                        <main className="dashboard-content dashboard-split">
                                            <div className="main-intel">
                                              <div className="grid-hero">
                                                  <div className="stat-card">
                                                      <Activity className="icon" />
                                                      <h3>Platform Identity</h3>
                                                      <p>{profile?.platforms?.chessCom}</p>
                                                  </div>
                                                  <div className="stat-card">
                                                      <Database className="icon" />
                                                      <h3>Tactical Archives</h3>
                                                      <p>{games.length} files digitized</p>
                                                  </div>
                                              </div>

                                              <section className="intel-deck">
                                                  <div className="section-header">
                                                      <h2>Recent Engagements</h2>
                                                  </div>

                                                  <div className="table-responsive">
                                                      <table className="intel-table">
                                                          <thead>
                                                              <tr>
                                                                  <th>Date</th>
                                                                  <th>Target</th>
                                                                  <th>Side</th>
                                                                  <th>Result</th>
                                                                  <th>Review</th>
                                                              </tr>
                                                          </thead>
                                                          <tbody>
                                                              {games.length === 0 ? (
                                                                  <tr><td colSpan="5" className="empty-row">Scanning archive...</td></tr>
                                                              ) : (
                                                                  games.map(game => {
                                                                      const isWhite = game.white === profile?.platforms?.chessCom?.toLowerCase();
                                                                      const opponent = isWhite ? game.black : game.white;
                                                                      const date = new Date(game.end_time * 1000).toLocaleDateString();

                                                                      return (
                                                                          <tr 
                                                                              key={game.id} 
                                                                              className={selectedGame?.id === game.id ? 'selected' : ''}
                                                                              onClick={() => setSelectedGame(game)}
                                                                          >
                                                                              <td className="dim">{date}</td>
                                                                              <td className="bold">{opponent}</td>
                                                                              <td><span className={`side-badge ${isWhite ? 'white' : 'black'}`}>{isWhite ? 'W' : 'B'}</span></td>
                                                                              <td><span className={`res-badge ${game.result}`}>{game.result}</span></td>
                                                                              <td><button className="row-action"><Play size={12}/> Review</button></td>
                                                                          </tr>
                                                                      );
                                                                  })
                                                              )}
                                                          </tbody>
                                                      </table>
                                                  </div>
                                              </section>
                                            </div>

                                            <AnimatePresence>
                                                {selectedGame && (
                                                    <motion.aside 
                                                        className="tactical-sidebar"
                                                        initial={{ opacity: 0, x: 20 }}
                                                        animate={{ opacity: 1, x: 0 }}
                                                        exit={{ opacity: 0, x: 20 }}
                                                    >
                                                        <TacticalViewer game={selectedGame} onClose={() => setSelectedGame(null)} />
                                                    </motion.aside>
                                                )}
                                            </AnimatePresence>
                                        </main>
                                    </div>
                            )}
                        </VerificationGuard>
                    )
                } />
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;
