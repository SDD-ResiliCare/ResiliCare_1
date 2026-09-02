import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Home, User, Settings, Headphones, Stethoscope } from 'lucide-react';
import { cn } from '../../lib/utils';

export function Sidebar() {
  const location = useLocation();

  const links = [
    { to: '/', icon: Home, label: 'Nurse' },
    { to: '/doctor', icon: Stethoscope, label: 'Doctor' },
    { to: '/patient', icon: User, label: 'Patient' },
    { to: '/admin', icon: Settings, label: 'Admin' },
  ];

  return (
    <aside className="w-24 flex flex-col items-center py-8 justify-between shrink-0 border-r border-white/5 relative z-20">
      <div className="flex flex-col items-center gap-12 w-full">
        {/* Logo Mark */}
        <div className="w-10 h-10 mb-2">
          <img src="/resilicare-mark.png" alt="ResiliCare" className="w-full h-full object-contain" />
        </div>

        {/* Navigation */}
        <nav className="flex flex-col gap-6 items-center w-full">
          {links.map((link) => {
            const isActive = link.to === '/' ? location.pathname === '/' : location.pathname.startsWith(link.to);
            return (
              <NavLink
                key={link.to}
                to={link.to}
                className={cn(
                  "w-12 h-12 rounded-full flex items-center justify-center transition-all relative group",
                  isActive 
                    ? "bg-white text-black shadow-lg" 
                    : "text-gray-500 hover:text-white"
                )}
                title={link.label}
              >
                <link.icon className={cn("w-[22px] h-[22px]", isActive && "fill-black/10")} strokeWidth={isActive ? 2.5 : 2} />
                
                {/* Tooltip */}
                <div className="absolute left-14 bg-[#1C1D21] text-white text-xs px-3 py-1.5 rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap border border-white/10 transition-opacity z-50 shadow-xl font-medium">
                  {link.label}
                </div>
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Bottom Icon */}
      <button className="w-12 h-12 rounded-full flex items-center justify-center text-gray-500 hover:text-white transition-all">
        <Headphones className="w-5 h-5" strokeWidth={2} />
      </button>
    </aside>
  );
}

