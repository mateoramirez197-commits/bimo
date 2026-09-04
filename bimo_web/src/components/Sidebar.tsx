import React from 'react';
import { 
  Stethoscope, 
  Calendar, 
  Users, 
  Settings, 
  LogOut, 
  FileText
} from 'lucide-react';

export default function Sidebar() {
  return (
    <div className="h-screen w-64 bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 shadow-2xl relative overflow-hidden">
      
      {/* Decorative Glow */}
      <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-cyan-500/10 to-transparent pointer-events-none" />

      {/* Header */}
      <div className="px-6 py-8 flex items-center gap-3.5">
        <div className="relative w-11 h-11 rounded-2xl bg-white/10 border border-white/20 p-[1px] shadow-2xl backdrop-blur-md flex items-center justify-center">
          <div className="w-full h-full bg-slate-950/70 rounded-[14px] flex items-center justify-center overflow-hidden">
            <svg className="w-7 h-7 text-white drop-shadow-md" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              {/* Ocho vertical (8) */}
              <path d="M20 20C22.2091 20 24 17.5376 24 14.5C24 11.4624 22.2091 9 20 9C17.7909 9 16 11.4624 16 14.5C16 17.5376 17.7909 20 20 20ZM20 20C22.4853 20 24.5 22.4624 24.5 25.5C24.5 28.5376 22.4853 31 20 31C17.5147 31 15.5 28.5376 15.5 25.5C15.5 22.4624 17.5147 20 20 20Z" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
              {/* Ocho horizontal entrelazado (Infinito) */}
              <path d="M20 20C20 17.7909 17.5376 16 14.5 16C11.4624 16 9 17.7909 9 20C9 22.2091 11.4624 24 14.5 24C17.5376 24 20 22.2091 20 20ZM20 20C20 17.5147 22.4624 15.5 25.5 15.5C28.5376 15.5 31 17.5147 31 20C31 22.4853 28.5376 24.5 25.5 24.5C22.4624 24.5 20 22.4853 20 20Z" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" opacity="0.9"/>
              {/* Nódulo central */}
              <circle cx="20" cy="20" r="1.5" fill="currentColor"/>
            </svg>
          </div>
        </div>
        <div>
          <div className="flex items-baseline gap-2">
            <h1 className="text-xl font-black text-white tracking-wider">BIMO</h1>
            <span className="text-[9px] bg-white/10 text-white/80 font-bold px-1.5 py-0.5 rounded border border-white/20">PRO</span>
          </div>
          <p className="text-xs text-slate-400 font-medium">by <span className="text-white font-bold">Matsword</span></p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 space-y-2 mt-4 relative z-10">
        <NavItem icon={<Stethoscope />} label="Dictado Médico" active />
        <NavItem icon={<Calendar />} label="Agenda" />
        <NavItem icon={<Users />} label="Pacientes" />
        <NavItem icon={<FileText />} label="Reportes" />
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800 relative z-10">
        <div className="px-4 py-3 bg-slate-800/50 rounded-xl flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-sm font-bold text-white">
            DR
          </div>
          <div>
            <p className="text-sm font-semibold text-white">Dr. Mateo</p>
            <p className="text-xs text-slate-400">Odontólogo</p>
          </div>
        </div>
        
        <nav className="space-y-1">
          <NavItem icon={<Settings />} label="Configuración" isFooter />
          <NavItem icon={<LogOut />} label="Cerrar Sesión" isFooter />
        </nav>
      </div>
    </div>
  );
}

function NavItem({ icon, label, active = false, isFooter = false }: { icon: React.ReactElement<any>, label: string, active?: boolean, isFooter?: boolean }) {
  return (
    <button 
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-300 group ${
        active 
          ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/10 text-cyan-400 font-medium shadow-[inset_2px_0_0_0_#22d3ee]' 
          : 'hover:bg-slate-800/50 hover:text-white'
      } ${isFooter ? 'py-2 text-sm' : ''}`}
    >
      <span className={`transition-transform duration-300 group-hover:scale-110 ${active ? 'text-cyan-400' : 'text-slate-400 group-hover:text-cyan-300'}`}>
        {React.cloneElement(icon, { size: isFooter ? 18 : 20 })}
      </span>
      <span>{label}</span>
    </button>
  );
}