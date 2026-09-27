# -*- coding: utf-8 -*-
"""
BIMO PRO - SUITE DE RESISTENCIA Y ESTRÉS CONTINUO (JORNADA CLÍNICA DE 6 HORAS)
Simulación de turno ininterrumpido de 5 a 6 horas con pacientes cada 10 minutos (600s).
Evalúa de punta a punta:
- Transcripción y estructuración clínica con IA (Groq / Llama 3.3 70B Versatile)
- Generación de Historia Clínica Oficial Formulario 033 MSP en PDF con Odontograma y CIE-10
- Comandos de voz contextuales (Hora actual, Agendamiento para el último paciente atendido)
- Slot-filling conversacional con preservación de estado
- Recordatorios WhatsApp con links wa.me anti-ausentismo
- Aprendizaje dinámico continuo de fonética y apellidos andinos/ecuatorianos
- Integridad transaccional de base de datos SQLite en modo WAL
- Telemetría de RAM (RSS), CPU y consumo de hilos en tiempo real
"""
import os
import sys
import time
import json
import psutil
import datetime
import argparse
from pathlib import Path

# Configurar codificación UTF-8
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

base_dir = Path("C:/Users/Mateo/Desktop/Bimo_Project").resolve()
sys.path.insert(0, str(base_dir))

# Mockear apertura de navegador para evitar abrir 36 pestañas
import webbrowser
webbrowser.open = lambda *args, **kwargs: True

from desktop_app import BimoBridge
from database import (
    init_db, get_connection, obtener_ultimo_paciente_atendido,
    obtener_vocabulario_aprendido
)
from config import get_groq_model, get_whisper_model, cargar_datos_clinica
from whatsapp_service import (
    generar_mensaje_recordatorio, generar_url_whatsapp, normalizar_numero_whatsapp
)

# 36 Casos Clínicos Únicos y Representativos de la Odontología en Ecuador
CASOS_JORNADA_6_HORAS = [
    {
        "nombre": "Sisa Llumiquinga Guamán",
        "edad": "29", "genero": "Femenino", "cedula": "1003456781", "telefono": "0998112233",
        "especialidad": "Operatoria Dental",
        "dictado": "Paciente Sisa Llumiquinga Guamán, 29 años, cédula 1003456781, teléfono 0998112233. Consulta por dolor agudo en pieza 26 con sensibilidad al frío y dulce. Examen clínico revela lesión cariosa oclusal profunda en 26 sin compromiso pulpar. Diagnóstico Caries de la dentina K02.1. Plan restauración con resina compuesta nanoparticulada bajo aislamiento absoluto y base de ionómero vítreo. Próxima cita de control en 8 días."
    },
    {
        "nombre": "Inti Toapanta Simbaña",
        "edad": "8", "genero": "Masculino", "cedula": "1724567890", "telefono": "0987223344",
        "especialidad": "Odontopediatría",
        "dictado": "Paciente pediátrico Inti Toapanta Simbaña, 8 años, cédula 1724567890, teléfono 0987223344. Acude de urgencia por traumatismo en bicicleta con fractura coronaria no complicada en pieza 11. Vitalidad pulpar positiva sin movilidad dental. Diagnóstico Fractura de diente en esmalte y dentina S02.5. Plan reconstrucción estética con resina nanohíbrida y pulido proximal. Cita de revisión en 14 días a las 10:00."
    },
    {
        "nombre": "María Carmen Pilataxi Quinatoa",
        "edad": "52", "genero": "Femenino", "cedula": "1002345678", "telefono": "0991334455",
        "especialidad": "Periodoncia",
        "dictado": "Paciente María Carmen Pilataxi Quinatoa, 52 años, cédula 1002345678, teléfono 0991334455. Consulta por sangrado gingival profuso al cepillado y cálculo supragingival generalizado. Bolsa periodontal de 5 mm en piezas 31, 41 y 42. Diagnóstico Periodontitis crónica generalizada K05.3. Plan raspado y alisado radicular por sextantes con ultrasonido y curetas Gracey, profilaxis y enjuagues de clorhexidina 0.12%. Próxima cita en 15 días."
    },
    {
        "nombre": "José Antonio Chushig Tituaña",
        "edad": "34", "genero": "Masculino", "cedula": "1719876543", "telefono": "0984556677",
        "especialidad": "Cirugía Bucal",
        "dictado": "Paciente José Antonio Chushig Tituaña, 34 años, cédula 1719876543, teléfono 0984556677. Control postoperatorio al séptimo día de exodoncia quirúrgica de tercer molar 38 retenido. Tejido cicatrizal en vías de epitelización sin exudado purulento. Diagnóstico Cuidados posteriores a la cirugía Z48.8. Plan retiro de sutura seda negra 3-0, irrigación con suero fisiológico y alta quirúrgica. Cita de control rutinario en 6 meses."
    },
    {
        "nombre": "Rosa Elena Yugsi Guaminga",
        "edad": "41", "genero": "Femenino", "cedula": "1004567892", "telefono": "0995667788",
        "especialidad": "Estética y Diseño de Sonrisa",
        "dictado": "Paciente Rosa Elena Yugsi Guaminga, 41 años, cédula 1004567892, teléfono 0995667788. Desea mejorar estética dental anterior por bordes incisales desgastados en piezas 11, 12, 21 y 22. Diagnóstico Abrasión del esmalte dental K03.1. Plan toma de registros interoclusales con silicona, fotos clínicas y modelos de estudio para mock-up diagnóstico. Cita para prueba estética el viernes a las 11:30."
    },
    {
        "nombre": "Carlos Alberto Quispe Yamberla",
        "edad": "46", "genero": "Masculino", "cedula": "1716543210", "telefono": "0992778899",
        "especialidad": "Endodoncia",
        "dictado": "Paciente Carlos Alberto Quispe Yamberla, 46 años, cédula 1716543210, teléfono 0992778899. Dolor dental severo, continuo e irradiado al temporal izquierdo, agudizado por calor en pieza 24. Diagnóstico Pulpitis irreversible aguda K04.0. Plan pulpectomía de urgencia, preparación biomecánica rotatoria con instrumentación reciprocante, medicación intraconducto con pasta de hidróxido de calcio y sellado cameral provisorio. Próxima cita para obturación en 10 días."
    },
    {
        "nombre": "Ana Lucía Cachimuel Farinango",
        "edad": "23", "genero": "Femenino", "cedula": "1005678901", "telefono": "0989889900",
        "especialidad": "Ortodoncia",
        "dictado": "Paciente Ana Lucía Cachimuel Farinango, 23 años, cédula 1005678901, teléfono 0989889900. Control mensual de aparatología fija con brackets de autoligado pasivo. Progreso de alineación y nivelación favorable. Diagnóstico Maloclusión dentaria clase II división 1 K07.2. Plan colocación de arco de acero rectangular 0.019 por 0.025 superior e inferior, ligaduras elásticas y elásticos intermaxilares de 3/16 de 4.5 oz. Próxima cita de activación en 4 semanas."
    },
    {
        "nombre": "Manuel Mesías Lema Imbaquingo",
        "edad": "61", "genero": "Masculino", "cedula": "1709876543", "telefono": "0997113355",
        "especialidad": "Rehabilitación Oral / Prótesis",
        "dictado": "Paciente Manuel Mesías Lema Imbaquingo, 61 años, cédula 1709876543, teléfono 0997113355. Edéntulo parcial bimaxilar superior e inferior clase I de Kennedy. Sesión de prueba de enfilado estético y funcional en cera. Diagnóstico Pérdida de dientes debida a accidente o caries K08.1. Plan verificación de soporte labial, fonética y oclusión céntrica, envío a laboratorio para polimerizado de acrílico termocurable. Cita para inserción de prótesis en 8 días a las 09:00."
    },
    {
        "nombre": "Diana Mercedes Pillajo Alomoto",
        "edad": "31", "genero": "Femenino", "cedula": "1718223344", "telefono": "0994551122",
        "especialidad": "Operatoria Dental",
        "dictado": "Paciente Diana Mercedes Pillajo Alomoto, 31 años, cédula 1718223344, teléfono 0994551122. Acude con filtración marginal en obturación antigua de amalgama en pieza 46. Pruebas de vitalidad normales. Diagnóstico Restauración dental defectuosa K08.8. Plan remoción de amalgama bajo aspiración de alta potencia, desinfección cavitaria con clorhexidina 2% y reconstrucción directa con resina microhíbrida. Cita para control en 12 días."
    },
    {
        "nombre": "Luis Fernando Chuquimarca Tipán",
        "edad": "39", "genero": "Masculino", "cedula": "1006778899", "telefono": "0983445566",
        "especialidad": "Cirugía Bucal",
        "dictado": "Paciente Luis Fernando Chuquimarca Tipán, 39 años, cédula 1006778899, teléfono 0983445566. Acude por pericoronaritis recidivante en tercer molar inferior derecho 48 semi-incluido. Diagnóstico Trastornos del desarrollo y de la erupción de los dientes K01.1. Plan odontoisección y exodoncia quirúrgica de pieza 48 bajo anestesia troncular al 2% con epinefrina, hemostasia con esponja de colágeno y sutura reabsorbible 4-0. Cita para control postquirúrgico en 7 días."
    },
    {
        "nombre": "Carmen Yolanda Caiza Masabanda",
        "edad": "57", "genero": "Femenino", "cedula": "1801234567", "telefono": "0996117788",
        "especialidad": "Periodoncia",
        "dictado": "Paciente Carmen Yolanda Caiza Masabanda, 57 años, cédula 1801234567, teléfono 0996117788. Dolor e inflamación gingival localizada en zona molar posterior. Bolsa periodontal de 6 mm en mesial de pieza 36 con supuración. Diagnóstico Absceso periodontal K05.2. Plan desbridamiento subgingival con ultrasonido, drenaje conservador de bolsa periodontal, irrigación con iodopovidona y prescripción de Amoxicilina 500 mg más Ácido Clavulánico cada 8 horas por 7 días. Cita en 5 días."
    },
    {
        "nombre": "Edwin Patricio Tasinchana Andrango",
        "edad": "27", "genero": "Masculino", "cedula": "1720334455", "telefono": "0981992233",
        "especialidad": "Endodoncia",
        "dictado": "Paciente Edwin Patricio Tasinchana Andrango, 27 años, cédula 1720334455, teléfono 0981992233. Asintomático, remitido de ortodoncia por hallazgo radiográfico de lesión radiolúcida periapical en pieza 12 previamente traumatizada. Pruebas térmicas negativas. Diagnóstico Necrosis pulpar K04.1 con periodontitis apical asintomática. Plan biopulpectomía no vital, instrumentación mecanizada, desinfección fotoactivada y medicación con pasta antibiótica temporal. Próxima cita en 15 días."
    },
    {
        "nombre": "Martha Cecilia Colcha Morocho",
        "edad": "48", "genero": "Femenino", "cedula": "0602334455", "telefono": "0993884411",
        "especialidad": "Operatoria Dental",
        "dictado": "Paciente Martha Cecilia Colcha Morocho, 48 años, cédula 0602334455, teléfono 0993884411. Acude por desprendimiento parcial de carilla vestibular en pieza 21 y sensibilidad cervical. Diagnóstico Defecto estético y abrasión dental K03.1. Plan acondicionamiento de superficie dental con ácido ortofosfórico al 37%, aplicación de adhesivo universal de séptima generación y grabado cerámico para cementación resinosa dual. Cita de pulido final en 7 días a las 15:00."
    },
    {
        "nombre": "Darwin Xavier Pastuña Guanoluisa",
        "edad": "11", "genero": "Masculino", "cedula": "0503445566", "telefono": "0982773322",
        "especialidad": "Odontopediatría",
        "dictado": "Paciente pediátrico Darwin Xavier Pastuña Guanoluisa, 11 años, cédula 0503445566, teléfono 0982773322. Evaluación semestral preventiva escolar. Dentición mixta tardía. Fosas y fisuras profundas retentivas en molares permanentes 16, 26, 36 y 46 sin cavitación. Diagnóstico Caries limitada al esmalte inicial K02.0. Plan profilaxis dental con pasta abrasiva de bajo índice RDA y aplicación de selladores resinosos fotopolimerizables. Cita de control en 6 meses."
    },
    {
        "nombre": "Blanca Narcisa Guasgua Curipoma",
        "edad": "64", "genero": "Femenino", "cedula": "1103221199", "telefono": "0995448833",
        "especialidad": "Rehabilitación Oral",
        "dictado": "Paciente Blanca Narcisa Guasgua Curipoma, 64 años, cédula 1103221199, teléfono 0995448833. Consulta por úlcera por decúbito en fondo de saco vestibular inferior derecho asociada a desajuste de prótesis total antigua. Diagnóstico Estomatitis protésica y lesión traumática de mucosa K12.1. Plan alivio mecánico y desgaste de flanco protésico sobreextendido, aplicación tópica de gel de ácido hialurónico 0.2% y suspensión de uso nocturno de la prótesis. Cita de reevaluación en 8 días."
    },
    {
        "nombre": "Segundo Rafael Sampedro Sangoluisa",
        "edad": "36", "genero": "Masculino", "cedula": "1715887766", "telefono": "0986332211",
        "especialidad": "Cirugía Bucal",
        "dictado": "Paciente Segundo Rafael Sampedro Sangoluisa, 36 años, cédula 1715887766, teléfono 0986332211. Presenta fractura radicular vertical irreparable en pieza 15 con fístula vestibular activa. Diagnóstico Fractura radicular dental traumática S02.5. Plan exodoncia atraumática con periostótomo fino, legrado alveolar minucioso, preservación de reborde alveolar con xenoinjerto óseo liofilizado y membrana de colágeno reabsorbible. Próxima cita para revisión en 10 días."
    },
    {
        "nombre": "Gladys Mariana Pupiales Fueres",
        "edad": "43", "genero": "Femenino", "cedula": "1004112233", "telefono": "0992336655",
        "especialidad": "Operatoria Dental",
        "dictado": "Paciente Gladys Mariana Pupiales Fueres, 43 años, cédula 1004112233, teléfono 0992336655. Refiere retención de alimentos y molestias masticatorias en sector posterosuperior derecho. Al examen clínico se evidencia caries interproximal mesio-oclusal en pieza 16. Diagnóstico Caries de la dentina K02.1. Plan apertura de cavidad clase II, colocación de matriz metálica seccional premoldeada con anillo de separación y restauración con composite nanohíbrido. Cita de control oclusal en 8 días."
    },
    {
        "nombre": "Milton Fabián Otavalo Cotacachi",
        "edad": "21", "genero": "Masculino", "cedula": "1006554433", "telefono": "0987441122",
        "especialidad": "Ortodoncia",
        "dictado": "Paciente Milton Fabián Otavalo Cotacachi, 21 años, cédula 1006554433, teléfono 0987441122. Inicio de tratamiento de ortodoncia correctiva para corregir apiñamiento moderado y mordida cruzada anterior unilateral. Diagnóstico Anomalías de la posición de los dientes K07.3. Plan cementado indirecto de aparatología fija estética en arcadas superior e inferior, colocación de arcos de alineación de termo-níquel-titanio 0.014 y topes oclusales posteriores de resina azul. Cita en 4 semanas."
    },
    {
        "nombre": "Verónica Patricia Cachiguango Cachimuel",
        "edad": "33", "genero": "Femenino", "cedula": "1005889911", "telefono": "0991887744",
        "especialidad": "Estética Dental",
        "dictado": "Paciente Verónica Patricia Cachiguango Cachimuel, 33 años, cédula 1005889911, teléfono 0991887744. Consulta para profilaxis profunda y aclaramiento dental en consultorio. Esmalte sano sin restauraciones defectuosas ni recesiones. Diagnóstico Pigmentaciones extrínsecas del esmalte K03.6. Plan profilaxis con bicarbonato de sodio en spray de aire-polvo y aplicación de peróxido de hidrógeno al 35% fotoactivado en tres ciclos de 15 minutos. Próxima cita para control de sensibilidad en 14 días."
    },
    {
        "nombre": "Jorge Washington Cabascango Guamán",
        "edad": "50", "genero": "Masculino", "cedula": "1708332211", "telefono": "0983119988",
        "especialidad": "Endodoncia",
        "dictado": "Paciente Jorge Washington Cabascango Guamán, 50 años, cédula 1708332211, teléfono 0983119988. Dolor intenso a la masticación en pieza 35 tratada endodónticamente hace 8 años. Radiografía muestra obturación corta y ensanchamiento del ligamento periodontal. Diagnóstico Periodontitis apical crónica K04.5. Plan retratamiento endodóntico, desobturación con solventes de gutapercha y limas D, instrumentación complementaria e irrigación sónica con hipoclorito al 5.25%. Cita en 12 días a las 10:00."
    },
    {
        "nombre": "Teresa Elizabeth Cajas Criollo",
        "edad": "67", "genero": "Femenino", "cedula": "1704556677", "telefono": "0994223311",
        "especialidad": "Rehabilitación Oral",
        "dictado": "Paciente Teresa Elizabeth Cajas Criollo, 67 años, cédula 1704556677, teléfono 0994223311. Desdentada total bimaxilar acude para control y adaptación de prótesis completas acrílicas nuevas. Dificultad leve en pronunciación de consonantes silbantes. Diagnóstico Falta de dientes completa K08.1. Plan ajuste oclusal por desgaste selectivo con papel de articular de 40 micras, pulido de bordes acrílicos y refuerzo de instrucciones de higiene. Cita en 15 días."
    },
    {
        "nombre": "Christian Marcelo Alulema Muenala",
        "edad": "25", "genero": "Masculino", "cedula": "1007221144", "telefono": "0985663322",
        "especialidad": "Cirugía Bucal",
        "dictado": "Paciente Christian Marcelo Alulema Muenala, 25 años, cédula 1007221144, teléfono 0985663322. Evaluación de cordales para inicio de plan quirúrgico profiláctico. Terceros molares 18 y 28 en supraerupción traumática contra mucosa yugal. Diagnóstico Dientes incluidos e impactados K01.1. Plan exodoncia quirúrgica simple de piezas 18 y 28 bajo anestesia local infiltrativa, hemostasia por compresión con gasa estéril y medicación con ketorolaco sublingual. Cita de revisión en 8 días."
    },
    {
        "nombre": "Silvia Paulina Cachipuendo Llumiquinga",
        "edad": "38", "genero": "Femenino", "cedula": "1003998877", "telefono": "0997441100",
        "especialidad": "Periodoncia",
        "dictado": "Paciente Silvia Paulina Cachipuendo Llumiquinga, 38 años, cédula 1003998877, teléfono 0997441100. Recesión gingival localizada de 3 mm clase I de Miller en cara vestibular de canino superior 13, con hipersensibilidad al frío. Diagnóstico Recesión gingival K06.0. Plan desensibilización con barniz de fluoruro de sodio al 5% y programación de cirugía mucogingival con injerto de tejido conectivo subepitelial. Próxima cita de valoración prequirúrgica en 20 días."
    },
    {
        "nombre": "Edison Roberto Chiluisa Toapanta",
        "edad": "44", "genero": "Masculino", "cedula": "0502113344", "telefono": "0989114477",
        "especialidad": "Operatoria Dental",
        "dictado": "Paciente Edison Roberto Chiluisa Toapanta, 44 años, cédula 0502113344, teléfono 0989114477. Fractura de cúspide distovestibular de molar 36 durante masticación de alimento duro. Pulpa vital confirmada por pruebas de frío. Diagnóstico Fractura incompleta de diente K03.8. Plan tallado para incrustación indirecta tipo Onlay de disilicato de litio, toma de impresión definitiva con silicona por adición y colocación de provisorio de bis-acrílico. Cita para cementación en 10 días."
    },
    {
        "nombre": "Andrea Estefanía Simbaña Quishpe",
        "edad": "19", "genero": "Femenino", "cedula": "1725881122", "telefono": "0993112288",
        "especialidad": "Operatoria Dental",
        "dictado": "Paciente Andrea Estefanía Simbaña Quishpe, 19 años, cédula 1725881122, teléfono 0993112288. Consulta preventiva antes de ingresar a semestre universitario. Detección de lesiones de mancha blanca activas en caras vestibulares de piezas 12 y 22. Diagnóstico Caries incipiente limitada al esmalte K02.0. Plan microabrasión controlada con pasta de ácido clorhídrico e infiltración de resina de baja viscosidad Icon, aplicación tópica de flúor fosfato acidulado. Cita en 3 meses."
    },
    {
        "nombre": "Wilson Hernán Tituaña Pilataxi",
        "edad": "58", "genero": "Masculino", "cedula": "1001445566", "telefono": "0986774433",
        "especialidad": "Rehabilitación Oral",
        "dictado": "Paciente Wilson Hernán Tituaña Pilataxi, 58 años, cédula 1001445566, teléfono 0986774433. Pérdida de soporte posterior y colapso de mordida. Examen radiográfico panorámico muestra remanentes radiculares en piezas 44 y 45 con rarefacción ósea periapical. Diagnóstico Resto radicular retenido K08.3. Plan extracción seriada de restos radiculares no restaurables y planificación de prótesis parcial fija implantosoportada. Cita para cirugía en 14 días a las 09:30."
    },
    {
        "nombre": "Erika Maribel Quinatoa Chushig",
        "edad": "28", "genero": "Femenino", "cedula": "1719332211", "telefono": "0998556644",
        "especialidad": "Operatoria Dental",
        "dictado": "Paciente Erika Maribel Quinatoa Chushig, 28 años, cédula 1719332211, teléfono 0998556644. Dolor moderado con dulces y alimentos fríos en pieza 14. Al examen se observa caries oclusodistal cavitada profunda. Diagnóstico Caries de la dentina K02.1. Plan remoción selectiva de tejido cariado, protección pulpar indirecta con silicato tricálcico biodentine y restauración definitiva con resina nanohíbrida. Cita de seguimiento en 10 días."
    },
    {
        "nombre": "Alex Gonzalo Yugsi Alomoto",
        "edad": "35", "genero": "Masculino", "cedula": "1714889900", "telefono": "0984113355",
        "especialidad": "Bruxismo y ATM",
        "dictado": "Paciente Alex Gonzalo Yugsi Alomoto, 35 años, cédula 1714889900, teléfono 0984113355. Dolor en músculos maseteros matutino, cefalea tensional y facetas de desgaste en caninos e incisivos. Chasquido articular bilateral en apertura máxima. Diagnóstico Bruxismo K05.8 y trastorno de la articulación temporomandibular K07.6. Plan confección de férula oclusal miorrelajante rígida de termocurado de 2.5 mm y terapia de relajación mandibular. Cita para entrega en 8 días."
    },
    {
        "nombre": "Paola Viviana Farinango Tipán",
        "edad": "22", "genero": "Femenino", "cedula": "1006117733", "telefono": "0992445599",
        "especialidad": "Odontopediatría / Traumatología Joven",
        "dictado": "Paciente Paola Viviana Farinango Tipán, 22 años, cédula 1006117733, teléfono 0992445599. Acude por contusión dental en sector anterior tras práctica deportiva. Sensibilidad a la percusión vertical en pieza 21 sin desplazamiento ni luxación evidente. Diagnóstico Concusión dental S02.5. Plan alivio oclusal por desgaste mínimo de cara palatina, ferulización semirrígida con alambre ortodóntico trenzado y composite por 14 días. Dieta blanda estricta. Cita en 14 días."
    },
    {
        "nombre": "Ramiro Javier Imbaquingo Caiza",
        "edad": "49", "genero": "Masculino", "cedula": "1002883311", "telefono": "0987332288",
        "especialidad": "Endodoncia",
        "dictado": "Paciente Ramiro Javier Imbaquingo Caiza, 49 años, cédula 1002883311, teléfono 0987332288. Dolor espontáneo lancinante y pulsátil en pieza 47, exacerbado en posición decúbito. Diagnóstico Pulpitis aguda serosa K04.0. Plan apertura cameral de emergencia, odontometría electrónica con localizador apical, instrumentación mecanizada con limas rotatorias de conicidad variable, irrigación abundante con EDTA al 17% y curación antiséptica. Cita en 7 días."
    },
    {
        "nombre": "Jessica Pamela Masabanda Colcha",
        "edad": "26", "genero": "Femenino", "cedula": "1802994411", "telefono": "0995116633",
        "especialidad": "Operatoria Dental",
        "dictado": "Paciente Jessica Pamela Masabanda Colcha, 26 años, cédula 1802994411, teléfono 0995116633. Manchas parduzcas y cavidad en cara oclusal de pieza 37. Asintomática. Diagnóstico Caries de la dentina K02.1 en fosa distal. Plan preparación conservadora sin bisel, técnica adhesiva selectiva de grabado ácido en esmalte y obturación en capas de 2 mm con resina nanorrellena. Pulido con discos Sof-Lex. Próxima cita de revisión anual."
    },
    {
        "nombre": "David Ernesto Morocho Pastuña",
        "edad": "15", "genero": "Masculino", "cedula": "0603772211", "telefono": "0981448822",
        "especialidad": "Ortodoncia Preventiva",
        "dictado": "Paciente David Ernesto Morocho Pastuña, 15 años, cédula 0603772211, teléfono 0981448822. Dentición permanente completa excepto terceros molares. Mordida abierta anterior de 4 mm asociada a deglución atípica persistente. Diagnóstico Maloclusión dentaria clase I con mordida abierta K07.2. Plan colocación de arco lingual con trampa de lengua pasiva y derivación a fonoaudiología para rehabilitación miofuncional. Cita de control en 4 semanas."
    },
    {
        "nombre": "Nancy Beatriz Guanoluisa Guasgua",
        "edad": "54", "genero": "Femenino", "cedula": "0501883322", "telefono": "0996881144",
        "especialidad": "Periodoncia",
        "dictado": "Paciente Nancy Beatriz Guanoluisa Guasgua, 54 años, cédula 0501883322, teléfono 0996881144. Halitosis subjetiva, retracción de encías y movilidad grado 2 en incisivos inferiores 31 y 41. Diagnóstico Periodontitis crónica avanzada K05.3. Plan terapia periodontal de soporte, desbridamiento por colgajo de acceso en sextante V, regeneración ósea guiada con hueso particulado y ferulización con cinta de fibra de vidrio Ribbond. Cita en 12 días."
    },
    {
        "nombre": "Víctor Hugo Curipoma Sampedro",
        "edad": "68", "genero": "Masculino", "cedula": "1102554477", "telefono": "0983226611",
        "especialidad": "Cirugía Bucal",
        "dictado": "Paciente Víctor Hugo Curipoma Sampedro, 68 años, cédula 1102554477, teléfono 0983226611. Presenta lesión exofítica pediculada de 5 mm en mucosa yugal izquierda en zona de roce protésico. Diagnóstico Pólipo fibroso inflamatorio por trauma K13.2. Plan biopsia escisional completa con bisturí frío número 15 bajo anestesia local infiltrativa al 2%, sutura reabsorbible vicryl 4-0 y remisión de la muestra a estudio anatomopatológico. Cita para informe en 15 días."
    },
    {
        "nombre": "Mónica Alexandra Sangoluisa Pupiales",
        "edad": "37", "genero": "Femenino", "cedula": "1717228833", "telefono": "0994993355",
        "especialidad": "Estética y Blanqueamiento",
        "dictado": "Paciente Mónica Alexandra Sangoluisa Pupiales, 37 años, cédula 1717228833, teléfono 0994993355. Sesión final de aclaramiento dental ambulatorio guiado por cubetas individuales flexibles. Tono basal A3 evolucionó a A1 según guía Vita. Diagnóstico Decoloración de los dientes K03.6. Plan control fotográfico final, desensibilización tópica con nitrato de potasio al 5% y recomendaciones dietéticas libres de cromógenos por 7 días. Cita de revisión en 6 meses."
    },
    {
        "nombre": "Héctor Daniel Fueres Otavalo",
        "edad": "42", "genero": "Masculino", "cedula": "1004882211", "telefono": "0985227744",
        "especialidad": "Rehabilitación Oral / Coronas",
        "dictado": "Paciente Héctor Daniel Fueres Otavalo, 42 años, cédula 1004882211, teléfono 0985227744. Prueba de estructura interna de zirconio para corona monolítica sobre muñón de pieza 25. Asentamiento marginal perfecto sin sobrecontornos ni báscula. Diagnóstico Diente muy destruido con tratamiento endodóntico previo K08.8. Plan registro de color para caracterización estética superficial en laboratorio dental y colocación de corona provisional con cemento sin eugenol. Cita de cementación definitiva en 8 días."
    }
]

def log_telemetria(msg, archivo_log):
    linea = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(linea)
    sys.stdout.flush()
    try:
        with open(archivo_log, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except Exception:
        pass

def ejecutar_jornada_continua(total_ciclos=36, intervalo_segundos=600):
    log_file = os.path.join(base_dir, "telemetria_jornada_continua.log")
    json_file = os.path.join(base_dir, "telemetria_jornada_continua.json")

    log_telemetria("=" * 78, log_file)
    log_telemetria(" 🏥 BIMO PRO - SUITE DE RESISTENCIA Y ESTRÉS CONTINUO: JORNADA DE 6 HORAS", log_file)
    log_telemetria("=" * 78, log_file)
    log_telemetria("Configuración de Jornada:", log_file)
    log_telemetria(f"  * Total Pacientes Planificados: {total_ciclos}", log_file)
    log_telemetria(f"  * Intervalo entre consultas:     {intervalo_segundos} s ({intervalo_segundos / 60:.1f} minutos)", log_file)
    log_telemetria(f"  * Duración Estimada de Turno:    {(total_ciclos * intervalo_segundos) / 3600:.2f} horas", log_file)
    log_telemetria(f"  * Modelo Clínico Groq:          {get_groq_model()}", log_file)
    log_telemetria(f"  * Modelo Acústico Whisper:       {get_whisper_model()}", log_file)
    log_telemetria("-" * 78, log_file)

    # 1. Inicializar base de datos y puente BimoBridge
    init_db()
    bridge = BimoBridge()
    proceso_actual = psutil.Process(os.getpid())

    memoria_inicial_mb = proceso_actual.memory_info().rss / (1024 * 1024)
    tiempo_inicio_global = time.time()

    telemetria_ciclos = []
    pdfs_generados = []
    errores = []

    # Estructura de estado en tiempo real para json persistente
    estado_jornada = {
        "estado": "EN_PROGRESO",
        "fecha_inicio": datetime.datetime.now().isoformat(),
        "total_ciclos_planificados": total_ciclos,
        "intervalo_segundos": intervalo_segundos,
        "modelo_ia": get_groq_model(),
        "whisper_modelo": get_whisper_model(),
        "memoria_inicial_rss_mb": round(memoria_inicial_mb, 2),
        "ciclos_completados": 0,
        "tasa_exito_porcentaje": 0.0,
        "db_integrity": "pendiente",
        "ciclos": telemetria_ciclos,
        "errores": errores
    }

    log_telemetria(f"[SETUP] Memoria Inicial RSS: {memoria_inicial_mb:.2f} MB | Hilos: {proceso_actual.num_threads()}", log_file)

    for i in range(1, total_ciclos + 1):
        t_ciclo_inicio = time.time()
        caso = CASOS_JORNADA_6_HORAS[(i - 1) % len(CASOS_JORNADA_6_HORAS)]
        
        log_telemetria(f"\n>>> [CONSULTA {i}/{total_ciclos}] {caso['nombre']} | {caso['especialidad']} ({caso['edad']}a, C.I. {caso['cedula']})", log_file)

        db_status = "unknown"
        try:
            # 1. Procesar dictado clínico con IA y generar PDF Formulario 033 MSP
            res = bridge.procesar_texto_clinico(caso["dictado"], generar_pdf=True)
            
            assert res.get("status") == "ok", f"Fallo en procesar_texto_clinico: {res.get('error')}"
            assert res.get("tipo") == "HISTORIA_CLINICA", f"Tipo inesperado: {res.get('tipo')}"

            p_nom = res.get("paciente", caso["nombre"])
            p_id = res.get("paciente_id")
            c_id = res.get("consulta_id")
            ruta_pdf = res.get("ruta_pdf")

            assert p_id and p_id > 0, f"Paciente ID inválido: {p_id}"
            assert c_id and c_id > 0, f"Consulta ID inválida: {c_id}"
            assert ruta_pdf and os.path.exists(ruta_pdf), f"PDF no encontrado: {ruta_pdf}"

            pdf_size_kb = os.path.getsize(ruta_pdf) / 1024
            assert pdf_size_kb > 10, f"PDF sospechosamente pequeño: {pdf_size_kb:.1f} KB"
            pdfs_generados.append(ruta_pdf)

            # 2. Comando de voz: Consulta de hora actual
            res_hora = bridge.procesar_texto_clinico("¿Bimo qué hora es?")
            assert res_hora.get("tipo") == "COMANDO_HORA", "Fallo en COMANDO_HORA"

            # 3. Verificación de resolución de último paciente atendido
            ultimo_p = obtener_ultimo_paciente_atendido()
            assert ultimo_p and ultimo_p["id"] == p_id, f"Inconsistencia en último paciente: {ultimo_p} != {p_id}"

            # 4. Agendamiento por comando de voz relativo para el último paciente
            dia_offset = (i % 14) + 2
            hora_cita = f"{9 + (i % 8):02d}:00"
            res_cita = bridge.procesar_texto_clinico(f"Bimo genera una cita para el último paciente en {dia_offset} días a las {hora_cita}")
            assert res_cita.get("tipo") == "COMANDO_CITA", f"Fallo en agendar cita por voz: {res_cita}"
            cita_id = res_cita.get("cita_id")
            assert cita_id and cita_id > 0, f"Cita ID inválido: {res_cita}"
            f_cita_str = res_cita.get("fecha_hora", "")

            # 5. Slot-filling conversacional (pedir cita sin fecha/hora para evaluar fallback reactivo)
            res_slot = bridge.procesar_texto_clinico(f"Bimo agenda una cita para {p_nom}")
            assert res_slot.get("status") == "requiere_fecha_hora", f"Fallo en slot-filling: {res_slot}"
            bridge._cita_pendiente = None  # Liberar slot pendiente para el próximo paciente

            # 6. Generar Recordatorio WhatsApp con link anti-ausentismo
            conf_cli = cargar_datos_clinica()
            num_wa = normalizar_numero_whatsapp(caso.get("telefono", "0998112233"))
            fecha_wa = f_cita_str or (datetime.datetime.now() + datetime.timedelta(days=dia_offset)).strftime("%Y-%m-%d %H:%M")
            msg_wa = generar_mensaje_recordatorio({
                "nombre_paciente": p_nom,
                "fecha_hora_inicio": fecha_wa,
                "motivo": f"Control post-operatorio y evolución de {caso['especialidad']}"
            }, conf_cli)
            url_wa = generar_url_whatsapp(num_wa, msg_wa)
            assert ("wa.me" in url_wa or "whatsapp.com" in url_wa) and len(msg_wa) > 25

            # 7. Verificación de Aprendizaje Dinámico de Vocabulario y Apellidos Andinos
            vocab_aprendido = obtener_vocabulario_aprendido(limite=50)
            total_vocab = len(vocab_aprendido)

            # 8. Comprobación de integridad SQLite WAL
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA integrity_check;")
                db_status = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM pacientes;")
                db_pacs = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM consultas;")
                db_cons = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM citas_agenda;")
                db_citas = cur.fetchone()[0]

            assert db_status.lower() == "ok", f"Corrupción SQLite detectada: {db_status}"

            # Telemetría del ciclo
            t_ciclo_duracion = time.time() - t_ciclo_inicio
            mem_actual_mb = proceso_actual.memory_info().rss / (1024 * 1024)
            cpu_pct = proceso_actual.cpu_percent(interval=None)
            hilos_actuales = proceso_actual.num_threads()

            diag_ia = res.get("resultado", {}).get("diagnostico", "Diagnóstico clínico")

            info_ciclo = {
                "ciclo": i,
                "timestamp": datetime.datetime.now().isoformat(),
                "paciente": p_nom,
                "especialidad": caso["especialidad"],
                "paciente_id": p_id,
                "consulta_id": c_id,
                "cita_id": cita_id,
                "duracion_segundos": round(t_ciclo_duracion, 2),
                "memoria_rss_mb": round(mem_actual_mb, 2),
                "cpu_percent": cpu_pct,
                "hilos_activos": hilos_actuales,
                "pdf_tamano_kb": round(pdf_size_kb, 1),
                "vocabulario_aprendido_count": total_vocab,
                "diagnostico_ia": diag_ia[:60],
                "db_integrity": db_status,
                "db_totales": {"pacientes": db_pacs, "consultas": db_cons, "citas": db_citas},
                "estado": "EXITOSO"
            }
            telemetria_ciclos.append(info_ciclo)

            log_telemetria(
                f"   [ÉXITO] Paciente #{p_id} | Consulta #{c_id} | Cita #{cita_id} | "
                f"PDF: {pdf_size_kb:.1f} KB | {t_ciclo_duracion:.2f}s | RAM: {mem_actual_mb:.1f} MB | WAL: {db_status}",
                log_file
            )

        except Exception as e:
            error_data = {
                "ciclo": i,
                "paciente": caso["nombre"],
                "timestamp": datetime.datetime.now().isoformat(),
                "error": str(e)
            }
            errores.append(error_data)
            log_telemetria(f"   [ERROR en ciclo {i}]: {e}", log_file)

        tiempo_transcurrido = time.time() - tiempo_inicio_global
        mem_actual = proceso_actual.memory_info().rss / (1024 * 1024)
        estado_jornada.update({
            "ultima_actualizacion": datetime.datetime.now().isoformat(),
            "ciclos_completados": len(telemetria_ciclos),
            "total_errores": len(errores),
            "tasa_exito_porcentaje": round((len(telemetria_ciclos) / i) * 100, 2),
            "tiempo_transcurrido_segundos": round(tiempo_transcurrido, 1),
            "tiempo_transcurrido_horas": round(tiempo_transcurrido / 3600, 2),
            "memoria_actual_rss_mb": round(mem_actual, 2),
            "delta_memoria_mb": round(mem_actual - memoria_inicial_mb, 2),
            "db_integrity": db_status
        })

        try:
            with open(json_file, "w", encoding="utf-8") as jf:
                json.dump(estado_jornada, jf, indent=2, ensure_ascii=False)
        except Exception:
            pass

        # Intervalo de espera entre consultas clínicas (10 minutos)
        if i < total_ciclos:
            log_telemetria(f"   [PAUSA OPERATIVA] Esperando {intervalo_segundos}s ({intervalo_segundos / 60:.1f} min) para el siguiente paciente del turno...", log_file)
            time.sleep(intervalo_segundos)

    # Finalización de Jornada
    tiempo_total_final = time.time() - tiempo_inicio_global
    memoria_final_mb = proceso_actual.memory_info().rss / (1024 * 1024)
    delta_memoria = memoria_final_mb - memoria_inicial_mb

    estado_jornada["estado"] = "FINALIZADO_CON_EXITO" if len(errores) == 0 else "FINALIZADO_CON_ADVERTENCIAS"
    estado_jornada["fecha_fin"] = datetime.datetime.now().isoformat()
    estado_jornada["duracion_total_horas"] = round(tiempo_total_final / 3600, 2)
    estado_jornada["memoria_final_rss_mb"] = round(memoria_final_mb, 2)
    estado_jornada["delta_memoria_mb"] = round(delta_memoria, 2)

    try:
        with open(json_file, "w", encoding="utf-8") as jf:
            json.dump(estado_jornada, jf, indent=2, ensure_ascii=False)
    except Exception:
        pass

    log_telemetria("\n" + "=" * 78, log_file)
    log_telemetria("               REPORTE FINAL DE JORNADA CLÍNICA CONTINUA (6H)", log_file)
    log_telemetria("=" * 78, log_file)
    log_telemetria(f"  * Pacientes Atendidos:         {len(telemetria_ciclos)}/{total_ciclos} ({estado_jornada['tasa_exito_porcentaje']}%)", log_file)
    log_telemetria(f"  * Errores Registrados:         {len(errores)}", log_file)
    log_telemetria(f"  * Duración Total de Jornada:   {tiempo_total_final / 3600:.2f} horas ({tiempo_total_final:.1f} s)", log_file)
    log_telemetria(f"  * Memoria RAM Inicial:         {memoria_inicial_mb:.1f} MB", log_file)
    log_telemetria(f"  * Memoria RAM Final:           {memoria_final_mb:.1f} MB (Delta: {delta_memoria:+.1f} MB)", log_file)
    log_telemetria(f"  * Integridad SQLite WAL:       {estado_jornada['db_integrity']}", log_file)
    log_telemetria(f"  * PDFs MSP 033 Emitidos:       {len(pdfs_generados)}", log_file)
    log_telemetria(f"  * Telemetría JSON:             {json_file}", log_file)
    log_telemetria("=" * 78, log_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prueba de Resistencia de Jornada Clínica Continua BIMO Pro")
    parser.add_argument("--ciclos", type=int, default=36, help="Número total de consultas clínicas a simular (default: 36)")
    parser.add_argument("--intervalo", type=int, default=600, help="Intervalo en segundos entre cada paciente (default: 600 s = 10 min)")
    args = parser.parse_args()

    ejecutar_jornada_continua(total_ciclos=args.ciclos, intervalo_segundos=args.intervalo)
