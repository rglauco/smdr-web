"""
Main entry point for SMDR Python application
Starts Flask web server and TCP SMDR server together
"""
import threading
import signal
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from server import tcpsmdrserver as tcpsmdr_module
TCPSMDRServer = tcpsmdr_module.TCPSMDRServer

# Create TCPSMDR server instance
smdr_server = TCPSMDRServer(port=3000)


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print("\n" + "=" * 60)
    print("Arresto applicazione...")
    print("=" * 60)

    # Stop SMDR server
    smdr_server.stop()

    print("\nApplicazione fermata. Chiudi il terminale per uscire dalla sessione.")
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def run_flask():
    """Run Flask application"""
    print("\nFlask Web Server avviato:")
    print(f"  - URL: http://localhost:5000")
    print(f"  - Porta: 5000")
    print(f"  - Database: SQLite3")
    print(f"  - Autenticazione: Nessuna (consulta anonima)")
    print("\n")


def main():
    """Main entry point"""
    print("=" * 60)
    print("SMDR Python Application - Portal")
    print("=" * 60)
    print()

    # Start TCP SMDR server in background thread
    print("TCP SMDR Server avviato:")
    print(f"  - Porta TCP: 3000")
    print(f"  - Log raw: Abilitato")
    print(f"  - Thread: Siamese")
    print()

    smdr_server.start()

    # Run Flask server in main thread
    run_flask()

    # Run Flask
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)


if __name__ == '__main__':
    main()