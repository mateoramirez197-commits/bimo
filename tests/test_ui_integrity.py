# scratch/verify_ui_integrity.py
import os
import re
import subprocess

with open('web_ui/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

required_ids = [
    # Navigation & Frame
    'customTitlebar', 'btnWinMin', 'btnWinMax', 'btnWinClose', 'topNavBar',
    'logoBadge', 'nav-dictado', 'nav-odontograma', 'nav-pacientes', 'nav-agenda',
    'nav-pdf', 'nav-config', 'nav-mobile', 'nav-widget', 'userAvatar', 'userDocName', 'userRole',
    
    # Tabs
    'tab-dictado', 'tab-odontograma', 'tab-agenda', 'tab-pacientes', 'tab-mobile', 'tab-pdf', 'tab-widget', 'tab-config',
    
    # Dictado & Clinical Record
    'cardPacNombre', 'cardPacDoc', 'cardPacTel', 'cardPacTelText',
    'cardPacDiag', 'cardPacPieza', 'cardPacPlan', 'cardPacSubplan',
    'cardPacCitaPago', 'cardPacSaldo', 'cardPacMed',
    'mainRecordButton', 'btnMainLabel', 'btnMicIconContainer', 'btnMicIcon',
    'recordStatusTitle', 'outerRing1', 'outerRing2',
    'btnToggleEscuchaActiva', 'badgeEscuchaDot', 'lblEscuchaActiva',
    'badgeEstadoDictado', 'badgeEstadoDot', 'lblEstadoDictado',
    'btnToggleOrto', 'btnPrintPdfBtn',
    'btnToggleMiniCal', 'miniCalendarDropdown', 'miniCalTitle', 'miniCalDiasGrid', 'miniCalCitasCount',
    'gridDientesSuperior', 'gridDientesInferior',
    
    # Modals
    'modalTerminos', 'modalPaciente', 'modalPacienteTitulo',
    'modalCita', 'modalReprogramarCita', 'modalRecordatoriosWhatsapp',
    'modalHistoriaClinica', 'modalEditarConsulta', 'modalCedulaObligatoria',
    
    # Login
    'loginScreen'
]

missing = []
for rid in required_ids:
    if f'id="{rid}"' not in content and f"id='{rid}'" not in content:
        missing.append(rid)

if missing:
    print("FAILED! Missing IDs:", missing)
else:
    print(f"PASSED! All {len(required_ids)} critical IDs are present.")

# Check for window.bimoApi in scripts
if 'window.bimoApi = ' in content:
    print("PASSED! window.bimoApi is defined.")
else:
    print("FAILED! window.bimoApi is missing!")

# Extract scripts and test syntax with Node
script_matches = re.findall(r'<script>([\s\S]*?)</script>', content)
print(f"Found {len(script_matches)} inline script blocks.")

import tempfile

for i, s in enumerate(script_matches):
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as sf:
        sf.write("function testCheckSyntax() {\n" + s + "\n}\nconsole.log('Script syntax OK');\n")
        temp_path = sf.name
    try:
        res = subprocess.run(['node', '-c', temp_path], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"PASSED! Script block {i} has valid JavaScript syntax.")
        else:
            print(f"FAILED! Script block {i} syntax error:\n", res.stderr)
    except Exception as e:
        print("Could not run node:", e)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
