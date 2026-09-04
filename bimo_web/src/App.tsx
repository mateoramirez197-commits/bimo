import Sidebar from "./components/Sidebar";
import { Mic, Upload } from "lucide-react";

function App() {
  return (
    <div className="flex h-screen bg-slate-950 font-sans overflow-hidden text-slate-100">
      {/* Menu Lateral Estilizado */}
      <Sidebar />

      {/* Contenido Principal (Simulando el Dictado Medico) */}
      <main className="flex-1 p-8 flex flex-col gap-6 relative">
        {/* Decorative Background Blob */}
        <div className="absolute top-[-10%] right-[-5%] w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        <header className="flex justify-between items-end relative z-10">
          <div>
            <h2 className="text-3xl font-bold text-white tracking-tight">Dictado Medico</h2>
            <p className="text-slate-400 mt-1">Escucha activa y generacion de historia clinica con IA.</p>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 bg-emerald-500/10 rounded-full border border-emerald-500/20">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-emerald-400 text-sm font-semibold">Sistema IA En Linea</span>
          </div>
        </header>

        {/* Layout 50/50 exacto como me pediste */}
        <div className="flex-1 flex gap-6 relative z-10">
          
          {/* Columna Izquierda: Control de Captura */}
          <div className="flex-1 bg-slate-900/80 backdrop-blur-md rounded-3xl border border-slate-800 p-8 flex flex-col shadow-2xl">
            <h3 className="text-cyan-400 text-sm font-bold tracking-wider mb-8">CONTROL DE CAPTURA</h3>
            
            <button className="w-full h-20 bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 rounded-2xl flex items-center justify-center gap-4 shadow-lg shadow-cyan-500/20 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]">
              <Mic className="text-white w-8 h-8" />
              <span className="text-white text-xl font-bold tracking-wide">INICIAR DICTADO MANUAL</span>
            </button>

            <button className="w-full h-14 mt-4 bg-transparent hover:bg-slate-800 border border-slate-700 rounded-xl flex items-center justify-center gap-3 transition-colors duration-300 text-slate-300 hover:text-white">
              <Upload className="w-5 h-5" />
              <span className="text-sm font-bold tracking-wide">ABRIR ULTIMO PDF</span>
            </button>

            {/* Estado Limpio */}
            <div className="mt-8 bg-slate-950/60 rounded-2xl border border-slate-800/80 p-6 flex-1 flex flex-col items-center justify-center text-center">
              <div className="w-3 h-3 rounded-full bg-cyan-400 mb-2 animate-pulse" />
              <p className="text-sm font-semibold text-slate-300">En espera</p>
            </div>
          </div>

          {/* Columna Derecha: Expediente */}
          <div className="flex-1 bg-slate-900/80 backdrop-blur-md rounded-3xl border border-slate-800 p-8 shadow-2xl flex flex-col">
            <h3 className="text-cyan-400 text-sm font-bold tracking-wider mb-6">HISTORIA CLINICA GENERADA</h3>
            <div className="space-y-4">
              <div className="h-4 w-3/4 bg-slate-800 rounded animate-pulse" />
              <div className="h-4 w-1/2 bg-slate-800 rounded animate-pulse" />
              <div className="h-4 w-5/6 bg-slate-800 rounded animate-pulse" />
              <div className="h-4 w-full bg-slate-800 rounded animate-pulse" />
            </div>
            
            <div className="mt-8 space-y-4 flex-1">
              <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider">Datos Extraidos en Tiempo Real</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
                  <div className="text-xs text-slate-500">Paciente</div>
                  <div className="text-sm font-semibold text-white mt-1">Esperando dictado...</div>
                </div>
                <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
                  <div className="text-xs text-slate-500">Tratamiento</div>
                  <div className="text-sm font-semibold text-white mt-1">Por determinar</div>
                </div>
                <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
                  <div className="text-xs text-slate-500">Piezas Dentales</div>
                  <div className="text-sm font-semibold text-white mt-1">Sin hallazgos</div>
                </div>
                <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
                  <div className="text-xs text-slate-500">Proxima Cita</div>
                  <div className="text-sm font-semibold text-white mt-1">Pendiente</div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}

export default App;
