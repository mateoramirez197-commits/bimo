# Parches BIMO (4 fases)

Archivos completos: `audio_feedback.py` y `drive_backup.py` (van tal cual). Aquí están los cambios puntuales para el resto.

---

## FASE 1 — `web_ui/index.html`

### 1.1 Helpers (ponlos al inicio de tu `<script>`, antes de `mostrarToast`)

```js
const $id = (id) => document.getElementById(id);
const setText = (id, v) => { const el = $id(id); if (el) el.innerText = v; };
const setHTML = (elOrId, html) => {
  const el = typeof elOrId === 'string' ? $id(elOrId) : elOrId;
  if (el) el.innerHTML = html;
};
const esc = (s) => String(s ?? '').replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
```

### 1.2 Los puntos que fallan (todos los IDs SÍ existen en el HTML → el `null` es de timing, ver nota al final)

```js
// mostrarToast
const msg = $id('toastMessage');
const icon = $id('toastIcon');
if (msg) msg.innerText = mensaje;
// ...en cada rama:  if (icon) icon.innerHTML = '<svg ...>';

// toggle maximizar (iconMaximizar)
const icon = $id('iconMaximizar');
if (icon) { icon.innerHTML = maximizado ? '<rect .../>' : '<rect .../>'; }

// cargarUltimoExpediente (cardPac*)
setText('cardPacNombre', exp.paciente || 'Paciente');
setText('cardPacDoc',    `CI: ${exp.documento || 'No registrada'} • ${exp.edad || ''}`);
setText('cardPacDiag',   exp.diagnostico || 'No especificado');
setText('cardPacPlan',   exp.plan || 'No especificado');
setText('cardPacCitaPago', exp.proxima_cita || 'Control regular');
setText('cardPacSaldo',  exp.pago || 'Al día');
setText('cardPacMed',    exp.receta || 'Sin medicación prescrita');

// cargarPacientes  -> el catch también usa tbody
} catch (e) {
  const tbody = $id('tablaPacientesBody');
  if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-rose-400">Error al cargar pacientes: ${esc(e)}</td></tr>`;
}
// dentro de renderTablaPacientes ya lo tienes protegido: bien.

// historiaConsultasTimeline, waListaContenedor: mismo patrón
const cont = $id('historiaConsultasTimeline');
if (!cont) return;

// selector de reprogramación
const sel = $id('reprogSelectCitaRef');
if (!sel) return;
// y en la línea ~3640:  const refId = ($id('reprogSelectCitaRef') || {}).value;

// PDFs (cargarPdfs / cargarPreview / paginación)
const cont = $id('listaPdfsContenedor');
if (!cont) return;
const badge = $id('badgeTotalPdfs');       if (badge) badge.innerText = pdfs.length;
const vacio = $id('previewPdfEmpty');      if (vacio) vacio.classList.remove('hidden');
const img   = $id('previewPdfImg');        if (img)   img.classList.add('hidden');
const ind   = $id('previewPageIndicator'); if (ind)   ind.innerText = `${currentPdfPageIndex + 1} / ${currentPdfPages.length}`;

// cargarCitas: los contadores también
setText('badgeTotalCitas', citas.length);
setText('miniCalCitasCount', `${citas.length} citas registradas`);
```

Grids del calendario (`agendaDiasGrid`, `miniCalDiasGrid`): `renderizarCalendarioAgenda` ya hace `if (!grid || !title) return;`. Verifica que `renderizarMiniCalendario` haga lo mismo (`if (!grid) return;`).

### 1.3 `renderizarListaCitas` + filtro de fecha

Reemplaza en `cargarCitas()` todo el bloque desde `if (!citas || citas.length === 0)` hasta el `.join('')` por `window.renderizarListaCitas(citas);` y el `catch` por la versión protegida.

```js
let filtroFechaCitas = null;   // 'YYYY-MM-DD' o null

window.renderizarListaCitas = function (citas) {
  const cont = $id('listaCitasContenedor');
  if (!cont) return false;                                   // pestaña aún no montada
  const lista = Array.isArray(citas) ? citas : [];

  if (lista.length === 0) {
    cont.innerHTML = '<div class="text-xs text-slate-500 text-center py-8">' +
      (filtroFechaCitas ? 'No hay citas para esa fecha.' : 'No hay citas pendientes agendadas.') + '</div>';
    return true;
  }

  const html = lista.map(c => {
    const f = c.fecha_hora_inicio || '';
    const hora = f.includes(' ') ? f.split(' ')[1] : f;
    const fechaCorta = f.includes(' ') ? f.split(' ')[0] : '';
    const badge = c.recordatorio_enviado
      ? `<span class="text-[9px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-1.5 py-0.5 rounded font-mono font-medium" title="Recordatorio enviado: ${esc(c.recordatorio_enviado_at || '')}">Enviado</span>`
      : '';
    const id = Number(c.id);                                  // fuerza número: nada de inyección en onclick
    return `
      <div class="p-4 bg-slate-950/70 rounded-2xl border border-slate-800 hover:border-slate-700 transition-colors flex justify-between items-center group">
        <div>
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold text-white">${esc(c.nombre_paciente)}</span>
            <span class="text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded font-mono font-bold">${esc(hora)}</span>
            ${badge}
          </div>
          <p class="text-xs text-slate-400 mt-1">${esc(c.descripcion || 'Consulta odontológica')}</p>
          <div class="text-[10px] text-slate-500 mt-0.5 font-mono">${esc(fechaCorta)}${c.telefono ? ` • Tel: ${esc(c.telefono)}` : ''}</div>
        </div>
        <div class="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onclick="enviarRecordatorioWhatsappCita(${id})" title="Recordatorio WhatsApp" class="p-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/30 text-emerald-400 cursor-pointer">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 5a2 2 0 012-2h3l2 5-2.5 1.5a11 11 0 005 5L14 12l5 2v3a2 2 0 01-2 2h-1C8.8 19 3 13.2 3 6V5z"/></svg>
          </button>
          <button onclick="abrirModalReprogramarCita(${id})" title="Reprogramar" class="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/30 text-amber-400 cursor-pointer">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          </button>
          <button onclick="cancelarCitaId(${id})" title="Cancelar" class="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/30 text-rose-400 cursor-pointer">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
      </div>`;
  }).join('');

  cont.innerHTML = html;                                      // una sola escritura al DOM
  return true;
};

function aplicarFiltroCitas() {
  const base = Array.isArray(citasCache) ? citasCache : [];
  const lista = filtroFechaCitas
    ? base.filter(c => (c.fecha_hora_inicio || '').startsWith(filtroFechaCitas))
    : base;
  window.renderizarListaCitas(lista);
}
window.filtrarCitasPorFecha = function (yyyy_mm_dd) {
  filtroFechaCitas = yyyy_mm_dd || null;
  aplicarFiltroCitas();
};
window.restablecerFiltroCitas = function () {
  filtroFechaCitas = null;
  const inp = $id('filtroFechaCitas');                        // opcional: <input type="date" id="filtroFechaCitas">
  if (inp) inp.value = '';
  aplicarFiltroCitas();
};

// en cargarCitas(): después de citasCache = citas; ...
//   aplicarFiltroCitas();   // (respeta el filtro activo)
// y el catch:
//   } catch (e) { const c = $id('listaCitasContenedor'); if (c) c.innerHTML = `<div class="text-xs text-rose-400 text-center py-6">Error al cargar citas: ${esc(e)}</div>`; }
```

### 1.4 Bug de fecha (zona horaria) en `abrirModalNuevaCita`

`new Date().toISOString()` da fecha **UTC**. En Ecuador (UTC-5), después de las 19:00 te propone el día siguiente.

```js
const d = new Date();
const hoy = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
```

### 1.5 Nota sobre la causa raíz del `null`

Los IDs existen una sola vez cada uno, así que no son typos: el JS corre antes de que el DOM esté listo, o Python llama `evaluate_js` (por ejemplo `actualizarTodosLosMenus`, `onVoiceClinicalProcessed`) antes de que cargue la página. Los `if` tapan el síntoma; añade además:

```js
window.__uiListo = false;
document.addEventListener('DOMContentLoaded', () => { window.__uiListo = true; });
```

---

## FASE 3 (frontend) — `ejecutarNavegacionVoz`

Usa `switchTab()` (ya cambia `hidden`, resalta el botón del menú y carga los datos). Cambiar `display` a mano rompería el estado del menú.

```js
window.ejecutarNavegacionVoz = function (accion, parametro) {
  const param = String(parametro || '').trim();
  switch (accion) {
    case 'abrir_agenda':
      switchTab('agenda');
      if (typeof irAHoyAgenda === 'function') irAHoyAgenda();
      break;

    case 'buscar_paciente': {
      switchTab('pacientes');
      const inp = $id('inputBuscarPaciente');
      if (inp) { inp.value = param; inp.focus(); }
      buscarPacientesEnVivo(param);
      break;
    }

    case 'abrir_odontograma':
      // No existe una vista de odontograma independiente: vive dentro del PDF del visor.
      switchTab('pdf');
      break;

    default:
      mostrarToast('No entendí a dónde ir.', 'warning');
  }
};
```

**Carrera de datos** (importante): `switchTab('pacientes')` dispara `cargarPacientes()` sin filtro y `buscarPacientesEnVivo` dispara otra con filtro; gana la que responda última. Protege `cargarPacientes` con un token:

```js
let _pacReqId = 0;
async function cargarPacientes(filtro = "") {
  const reqId = ++_pacReqId;
  // ... obtener lista ...
  if (reqId !== _pacReqId) return;     // llegó una petición más nueva: descarta esta
  pacientesCache = lista;
  renderTablaPacientes(lista);
}
```

---

## FASE 2 — `desktop_app.py`

```python
# import (línea ~75)
from audio_feedback import sonar_inicio_dictado, sonar_fin_dictado, sonar_confirmacion_exito, sonar_error
```

Bloque `IGNORAR` en `procesar_texto_clinico`:

```python
        if tipo == "IGNORAR":
            try:
                sonar_error()
            except Exception:
                pass
            return { ...igual que ahora... }
```

`except` principales (añade `sonar_error()` en un try/except mínimo en cada uno):
`iniciar_grabacion`, `detener_y_procesar`, `_ejecutar_comando_detectado`, y el `if not stream_iniciado:` de `_grabar_audio_loop`. También conviene en los `return {"status": "error"...}` de "No se detectó audio / voz inteligible".

---

## FASE 3 — `ai_engine.py`

### 3.1 Resolver determinista (0 ms, 0 tokens, como tus otros `resolver_*`)

```python
import re

_NAV_PREFIJO = r"(?:abre|abrir|muestra|mostrar|ve a|ir a|llévame a|llevame a|busca|buscar|encuentra|encontrar)"

def resolver_navegacion_ui(texto_crudo: str) -> dict | None:
    t = texto_crudo.lower().replace("bimo", "").strip(" ,.?!¿¡")
    t = re.sub(r"^(hola|oye|por favor)[, ]+", "", t)
    if len(t.split()) > 10:                    # un dictado clínico largo NUNCA es navegación
        return None

    m = re.match(rf"^{_NAV_PREFIJO}\s+(?:al\s+|a\s+la\s+|el\s+|la\s+)?(?:paciente|expediente|historia(?: clínica)?(?: de)?)\s+(.+)$", t)
    if m:
        return {"tipo": "NAVEGACION_UI", "accion": "buscar_paciente", "parametro": m.group(1).strip().title()}

    if re.match(rf"^{_NAV_PREFIJO}\s+(?:el\s+|la\s+|mi\s+)?odontograma\b", t):
        return {"tipo": "NAVEGACION_UI", "accion": "abrir_odontograma", "parametro": ""}

    if re.match(rf"^{_NAV_PREFIJO}\s+(?:la\s+|mi\s+|el\s+)?(?:agenda|citas|calendario)\b", t):
        return {"tipo": "NAVEGACION_UI", "accion": "abrir_agenda", "parametro": ""}
    return None
```

En `procesar_comando_o_dictado`, justo después de `cmd_hora`:

```python
    nav = resolver_navegacion_ui(texto_crudo)
    if nav:
        return nav
```

### 3.2 Prompt de Groq (fallback para frases que el regex no cubre)

Añade tras la intención 7 (`IGNORAR`):

```
8. NAVEGACION_UI: Orden CORTA y directa para mover la interfaz (ej: 'abre la agenda', 'muéstrame el odontograma', 'busca al paciente Juan Pérez', 'ir a pacientes'). NUNCA si el texto contiene síntomas, piezas dentales, diagnóstico, tratamiento o filiación: eso es HISTORIA_CLINICA.
```

Y la plantilla de salida, junto a las demás:

```
Si es NAVEGACION_UI:
{{
    "tipo": "NAVEGACION_UI",
    "accion": "abrir_agenda | buscar_paciente | abrir_odontograma",
    "parametro": "Nombre del paciente si aplica, si no cadena vacía"
}}
```

(Elige UNA acción; no dejes las tres con `|` en producción si el modelo las copia literal: por eso validamos la lista blanca en `desktop_app.py`.)

Comprueba también la cadena de post-procesado después del `json.loads` (líneas ~1458-1650 de ese archivo): que un `tipo` desconocido no se reencamine a `HISTORIA_CLINICA`.

---

## FASE 3 — `desktop_app.py`

### 3.3 Rama en `procesar_texto_clinico` (ANTES de `if tipo == "IGNORAR"`)

Esto es crítico: hoy, después del bloque `IGNORAR`, el código hace `tipo = "HISTORIA_CLINICA"` incondicionalmente. Sin esta rama, "abre la agenda" crearía un paciente `Paciente_Consulta` y un PDF.

```python
        if tipo == "NAVEGACION_UI":
            accion = str(resultado_ia.get("accion", "")).strip()
            if accion not in ("abrir_agenda", "buscar_paciente", "abrir_odontograma"):
                try:
                    sonar_error()
                except Exception:
                    pass
                return {"status": "warning", "tipo": "IGNORAR", "texto": texto,
                        "resultado": resultado_ia, "mensaje": "No entendí a qué pantalla ir."}
            return {"status": "ok", "tipo": "NAVEGACION_UI", "texto": texto,
                    "accion": accion,
                    "parametro": str(resultado_ia.get("parametro") or "").strip(),
                    "resultado": resultado_ia, "mensaje": "Navegando..."}
```

### 3.4 Rama en `_ejecutar_comando_detectado`

Usa `json.dumps` en lugar de `'{parametro}'`: con "O'Brien" o comillas, el f-string original rompe el JavaScript (y permite inyección).

```python
                elif tipo == "NAVEGACION_UI":
                    accion = resp.get("accion", "")
                    parametro = resp.get("parametro", "") or ""
                    self._window.evaluate_js(
                        f"if (window.ejecutarNavegacionVoz) "
                        f"window.ejecutarNavegacionVoz({json.dumps(accion)}, {json.dumps(parametro)});"
                    )
                    sonar_confirmacion_exito()
                    return          # no llamar a onVoiceClinicalProcessed para navegación
```

Mismo problema ya existente (arréglalo de paso):

```python
# antes:  'No se encontró cita activa para {nom_pac}'   y   'Te escucho {nom_doc}...'
# después:
self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(f'No se encontró cita activa para {nom_pac}')}, 'error');")
self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(f'Te escucho {nom_doc}...')}, 'info');")
```

---

## FASE 4 — `calendar_sync.py`

```python
import json   # arriba, junto a los otros imports

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive.file',
]   # OJO: URL en texto plano, sin el formato [texto](link) de markdown
_GOOGLE_CREDS = None


def _token_tiene_todos_los_scopes(token_path):
    try:
        with open(token_path, encoding='utf-8') as f:
            otorgados = set(json.load(f).get('scopes') or [])
        return set(SCOPES).issubset(otorgados)
    except Exception:
        return False


def obtener_credenciales_google():
    """Credenciales vigentes con scope de Drive, o None."""
    if _GOOGLE_CREDS and _GOOGLE_CREDS.valid and 'https://www.googleapis.com/auth/drive.file' in (_GOOGLE_CREDS.scopes or []):
        return _GOOGLE_CREDS
    return None
```

En `init_google_calendar`, **antes** de `if os.path.exists(token_path):`:

```python
    # El token.json actual solo tiene scope de Calendar: sin esto Drive dará 403 para siempre.
    # Se fuerza UNA re-autorización, pero solo si hay credentials.json para poder hacerla.
    if os.path.exists(token_path) and os.path.exists(cred_path) and not _token_tiene_todos_los_scopes(token_path):
        try:
            os.remove(token_path)
        except Exception:
            pass
```

Y donde termina bien (`if creds and creds.valid:`), antes del `build(...)`:

```python
    global _GOOGLE_CREDS
    _GOOGLE_CREDS = creds
```

(Declara `global _CALENDAR_SERVICE, _DOCTOR_EMAIL, _GOOGLE_CREDS` en la firma de la función en vez de un `global` suelto.)

Además, Google permite desmarcar permisos sueltos en la pantalla de consentimiento: si el doctor desmarca Drive, `token.json` queda sin ese scope y `obtener_credenciales_google()` devuelve `None`; el respaldo simplemente no corre.

---

## FASE 4 — `desktop_app.py` (disparo del respaldo)

En la clase `BimoBridge`:

```python
    def _disparar_respaldo_drive(self, al_cerrar=False):
        """Silencioso: nunca interrumpe login ni cierre."""
        try:
            from calendar_sync import obtener_credenciales_google
            from drive_backup import respaldar_en_drive
            creds = obtener_credenciales_google()
            if not creds:
                return None
            # passphrase=None => zip sin cifrar. Recomendado: leerla de la bóveda/ajustes.
            return respaldar_en_drive(creds, daemon=not al_cerrar)
        except Exception as e:
            print(f"[DRIVE BACKUP WARN] {e}")
            return None
```

Login (en `autenticar` y en `autenticar_pin`, justo antes del `return {"status": "ok", ...}`):

```python
                self._disparar_respaldo_drive()
```

Cierre (dentro de `iniciar_desktop()`, junto a `window.events.closed += on_closed`). Usa `closing`, no `closed`: al llegar a `closed` el proceso ya se está yendo y un hilo daemon muere a mitad de subida.

```python
    def on_closing():
        t = bridge._disparar_respaldo_drive(al_cerrar=True)
        if t:
            t.join(timeout=25)      # máx. 25 s; el throttle evita subir si no hubo cambios

    window.events.closing += on_closing
```

Dependencias: `google-api-python-client`, `google-auth-oauthlib` (ya las tienes por Calendar) y `cryptography` (ya la usas para la bóveda). En Google Cloud Console: habilitar **Google Drive API** en el mismo proyecto de `credentials.json`.
