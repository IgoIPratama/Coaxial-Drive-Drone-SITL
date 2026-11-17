#!/usr/bin/env bash
# run_sitl.sh - peluncur 2 terminal untuk SITL Single-EDF (jalankan perintah, bukan skrip ini apa adanya, bila ragu)
# Prasyarat: ArduPilot sudah di-clone & prereq terpasang (lihat README_SITL.md). Ubah ARDUPILOT_DIR.
ARDUPILOT_DIR="${ARDUPILOT_DIR:-$HOME/ardupilot}"
HERE="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-normal}"   # normal | freeze | autosign

echo "=== Terminal A: backend fisika (mode: $MODE) ==="
echo "python3 $HERE/physics_backend.py --vehicle $HERE/vehicle.json --mode $MODE --log $HERE/run_log.csv"
echo
echo "=== Terminal B: ArduPilot SITL ==="
echo "cd $ARDUPILOT_DIR && Tools/autotest/sim_vehicle.py -v ArduCopter -f singlecopter --model JSON:127.0.0.1 --add-param-file=$HERE/edf_tvc.parm --console --map -w"
echo
echo "Jika argumen --model/-f ditolak pada versi-mu, cek: sim_vehicle.py --help"
echo
if [ "${2:-}" = "--start-backend" ]; then
  exec python3 "$HERE/physics_backend.py" --vehicle "$HERE/vehicle.json" --mode "$MODE" --log "$HERE/run_log.csv"
fi
