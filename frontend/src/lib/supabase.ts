import { createClient } from '@supabase/supabase-js';

const supabaseUrl = (import.meta as any).env.VITE_SUPABASE_URL;
const supabaseAnonKey = (import.meta as any).env.VITE_SUPABASE_ANON_KEY;

// Keep the app renderable in local/demo mode; authentication will report a
// useful error if credentials are not configured instead of crashing startup.
const configuredUrl = supabaseUrl || 'http://127.0.0.1:54321';
const configuredAnonKey = supabaseAnonKey || 'missing-anon-key';

export const supabase = createClient(configuredUrl, configuredAnonKey);
