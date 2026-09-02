import React from 'react';
import { Link } from 'react-router-dom';
import { Activity, User, Settings, ArrowRight } from 'lucide-react';

export function RoleSelection() {
  const roles = [
    {
      to: '/nurse',
      icon: Activity,
      title: 'Triage Dashboard',
      description: 'Nurse & MD Interface to review AI suggestions, monitor queue, and override ESI scores.',
      color: 'text-[#D6FF38]',
      bg: 'bg-[#D6FF38]/10'
    },
    {
      to: '/admin',
      icon: Settings,
      title: 'Operations Admin',
      description: 'Hospital Administrator Interface to manage operational profiles and surge protocols.',
      color: 'text-blue-400',
      bg: 'bg-blue-400/10'
    },
    {
      to: '/patient',
      icon: User,
      title: 'Patient Intake Kiosk',
      description: 'Patient-facing Interface for initial complaint entry and AI differential processing.',
      color: 'text-purple-400',
      bg: 'bg-purple-400/10'
    }
  ];

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] max-w-4xl mx-auto w-full">
      <div className="text-center mb-16 space-y-4">
        <h1 className="text-4xl md:text-5xl font-light tracking-tight text-white">
          Welcome to <span className="font-semibold text-[#D6FF38]">ResiliCare</span>
        </h1>
        <p className="text-gray-400 text-lg max-w-xl mx-auto">
          AI-assisted ER triage and clinical operations management system. Select your role to continue.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full">
        {roles.map((role) => (
          <Link
            key={role.to}
            to={role.to}
            className="group relative flex flex-col p-8 rounded-[2rem] bg-[#1C1D21] border border-[#2A2B30] hover:border-[#D6FF38]/50 hover:bg-[#25262B] transition-all duration-300 hover:-translate-y-1 overflow-hidden"
          >
            <div className={`w-14 h-14 rounded-2xl ${role.bg} flex items-center justify-center mb-6`}>
              <role.icon className={`w-7 h-7 ${role.color}`} />
            </div>
            <h2 className="text-xl font-medium text-white mb-3">{role.title}</h2>
            <p className="text-sm text-gray-400 leading-relaxed mb-8 flex-1">
              {role.description}
            </p>
            <div className="flex items-center text-sm font-medium text-gray-300 group-hover:text-white transition-colors">
              Access portal
              <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
            </div>
            
            {/* Decorative background gradient */}
            <div className={`absolute -bottom-20 -right-20 w-40 h-40 ${role.bg} blur-3xl rounded-full opacity-0 group-hover:opacity-50 transition-opacity duration-500`} />
          </Link>
        ))}
      </div>
    </div>
  );
}
