import React from 'react';
import { Sidebar } from './Sidebar';

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-full bg-[#111215] text-white overflow-hidden font-sans relative">
      <Sidebar />
      <main className="flex-1 flex overflow-hidden relative">
        {children}
      </main>
    </div>
  );
}
