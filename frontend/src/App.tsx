import React, { StrictMode, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { DashboardLayout } from './components/layout/DashboardLayout';
import { NurseDashboard } from './pages/NurseDashboard';
import { AdminDashboard } from './pages/AdminDashboard';
import { PatientDashboard } from './pages/PatientDashboard';
import { DoctorDashboard } from './pages/DoctorDashboard';
import { supabase } from './lib/supabase';

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('authToken'));

  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  if (!token) {
    const handleAuth = async (e: React.FormEvent) => {
      e.preventDefault();
      setLoading(true);
      setErrorMsg('');

      try {
        const { data, error } = isLogin 
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({ email, password });

        if (error) throw error;

        if (data.session) {
          localStorage.setItem('authToken', data.session.access_token);
          setToken(data.session.access_token);
          window.location.reload();
        } else if (!isLogin) {
          setErrorMsg('Signup successful! You may need to verify your email, or you can log in now.');
        }
      } catch (err: any) {
        setErrorMsg(err.message || 'An error occurred during authentication');
      } finally {
        setLoading(false);
      }
    };

    return (
      <div className="min-h-screen bg-[#0A0A0B] text-white flex items-center justify-center p-4">
        <div className="bg-[#121722] border border-[#26344A] p-8 rounded-[2rem] w-full max-w-md shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-[#8BE8E2]/10 blur-3xl rounded-full pointer-events-none" />
          
          <h2 className="text-3xl font-bold mb-2 text-center text-white">{isLogin ? 'Welcome Back' : 'Create Account'}</h2>
          <p className="text-gray-400 text-sm mb-8 text-center">{isLogin ? 'Sign in to ResiliCare' : 'Join ResiliCare staff network'}</p>
          
          {errorMsg && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm p-3 rounded-xl mb-6 text-center">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleAuth} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Email</label>
              <input 
                type="email" 
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="staff@resilicare.com" 
                className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-[#8BE8E2] transition-colors"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Password</label>
              <input 
                type="password" 
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••" 
                className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-[#8BE8E2] transition-colors"
                required
              />
            </div>
            <button 
              type="submit" 
              disabled={loading}
              className="w-full bg-[#8BE8E2] text-black font-bold py-3.5 rounded-xl hover:bg-[#55D9D5] transition-colors mt-4 disabled:opacity-50"
            >
              {loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Sign Up')}
            </button>
          </form>

          <p className="mt-8 text-center text-sm text-gray-400">
            {isLogin ? "Don't have an account? " : "Already have an account? "}
            <button 
              onClick={() => { setIsLogin(!isLogin); setErrorMsg(''); }} 
              className="text-[#8BE8E2] font-semibold hover:underline"
            >
              {isLogin ? 'Sign Up' : 'Sign In'}
            </button>
          </p>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <DashboardLayout>
        <Routes>
          <Route path="/" element={<NurseDashboard />} />
          <Route path="/patient" element={<PatientDashboard />} />
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/doctor" element={<DoctorDashboard />} />
        </Routes>
      </DashboardLayout>
    </BrowserRouter>
  );
}
