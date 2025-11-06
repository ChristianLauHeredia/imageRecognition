#!/usr/bin/env python3
"""Script de prueba para verificar que el servidor puede iniciar"""

import sys

try:
    print("1. Importando módulos...")
    from app.main import app
    print("✓ app.main importado correctamente")
    
    from app.agent_def import vision_analyzer, run_vision
    print("✓ app.agent_def importado correctamente")
    
    from app.schemas import VisionResult, BBox
    print("✓ app.schemas importado correctamente")
    
    print("\n2. Verificando que vision_analyzer está definido...")
    if vision_analyzer:
        print("✓ vision_analyzer está definido")
    else:
        print("✗ vision_analyzer no está definido")
        sys.exit(1)
    
    print("\n3. Intentando iniciar servidor...")
    import uvicorn
    print("✓ uvicorn disponible")
    print("\n✓ Todo listo! Puedes ejecutar: uvicorn app.main:app --reload")
    
except ImportError as e:
    print(f"✗ Error de importación: {e}")
    print("\nAsegúrate de instalar las dependencias:")
    print("pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


