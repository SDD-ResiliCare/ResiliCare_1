import React from 'react';
import { Sidebar } from './Sidebar';

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-center h-screen bg-[#E5E9F0] p-4 lg:p-8 overflow-hidden font-sans">
      <div className="flex h-full w-full max-w-[1600px] bg-[#111215] text-white rounded-[2.5rem] shadow-[0_20px_50px_rgba(0,0,0,0.3)] overflow-hidden border border-[#202124] relative">
        <Sidebar />
        <main className="flex-1 flex overflow-hidden relative">
          {children}
        </main>
      </div>
    </div>
  );
}
