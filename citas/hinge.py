#!/usr/bin/env python3
"""hinge.py chats | chat NOMBRE | perfil NOMBRE | enviar NOMBRE "texto"  (ver android_enviar.py)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from android_enviar import main
main("hinge", sys.argv[1:])
