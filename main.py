
from session_manager import SessionManager
from storage_manager import StorageManager
from map_handler import (from_filename_get_floor, get_coordinates_from_map,  
                        calibrate_distance, get_distance, 
                        get_two_coordinates_from_map, plot_rssi_on_map)

from scanner import WifiScanner
import os 
import json
import statistics as st
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def print_menu():
    print("\n==========================================")
    print("HERRAMIENTA DE MEDIDA Y MAPEO DE WIFI (CLI)")
    print("===========================================")
    print("1 - Cambiar de proyecto")
    print("2 - Ajustar los tags del proyecto")
    print("3 - Mapear coordenadas de las posteriores medidas sobre el plano de la infraestructura de la organización en los tags")
    print("4 - Realizar medidas sobre las coordenadas")
    print("5 - Calibrar metros/píxel")
    print("6 - Obtener MACs de los BSSID a los que nos conectamos en las mediciones")
    print("7 - Plotear RSSI de un AP sobre el plano")
    print("8 - Obtener gráfica de un APP (RSSI en función de la distancia)")
    print("9 - Tabla de APs en un punto/zona")   

def cli(): 

    session_mgr = SessionManager()
    storage_mgr = StorageManager()
    print(f"\n[*] Proyecto: {session_mgr.config.get('project_name')}")
    print(f"[*] {session_mgr.config.get('building')} | {session_mgr.config.get('floor')} | {session_mgr.config.get('room')}")   
    while True:
        try:
            print_menu()
            selected_mode:int = int(input("Seleccione un modo: "))
        except EOFError: # Si ctrl D entonces salir
            break
        except ValueError:
            print("Entrada inválida.")
            continue

        if selected_mode == 1:
            """
            * Si se abre un proyecto existente, se hará un append en StorageManager.save_measurement, cuando se realizen las medidas
            """
            current = session_mgr.config.get("project_name")
            new_name = input(f"Nuevo nombre de proyecto [{current}]: ").strip()
            if new_name:
                session_mgr.update_tags({"project_name": new_name, "coordinates": {"x": 0, "y": 0}})
                print(f"[OK] Proyecto cambiado a: {new_name}")
                print("[!] Coordenadas reseteadas. Use el modo 3 para mapear el nuevo punto.")
            else:
                print("→ Sin cambios.")
        
        
        elif selected_mode == 2:
            """
            * Si se pulsa enter, entonces se guardará "" y queda el valor entre corchetes.
            * Sólo escribir en las que se desea cambiar, ver método session_mgr.update_tags
            """
            c = session_mgr.config
            building = input(f"Edificio [{c.get('building')}]: ").strip()
            room = input(f"Aula/Sala [{c.get('room')}]: ").strip()
            corridor = input(f"Pasillo [{c.get('corridor')}]: ").strip()
            point_id = input(f"Punto de medida [{c.get('point_id')}]: ").strip()
            orientation = input(f"Orientación [{c.get('orientation')}]: ").strip()

            new_tags = {
                "building": building,
                "room": room,
                "corridor": corridor,
                "point_id": point_id,
                "orientation": orientation,
            }
            session_mgr.update_tags(new_tags)
            print("[OK] Tags actualizados.")

        elif selected_mode == 3:
            """
            * Se almacenan en la sesión los últimas coordenadas seleccionadas.
            * Por eso es importante, si se cambia de medida actualizarlas antes.
            """
            filename: str = input("Introduzca el nombre de la imagen: ").strip()
            path:str = os.path.join(BASE_DIR, "img", filename)
            print("Extrayendo la planta del nombre del archivo(...)\n")
            floor:int = from_filename_get_floor(filename)
            print(f"Planta a analizar: {floor}")
            print("Abriendo plano para selección del punto de medida(...)\n")
            coordinates: tuple[int, int] | None = get_coordinates_from_map(path,floor)
            if coordinates is not None:
                session_mgr.update_tags({
                    "floor": str(floor),
                    "coordinates": {"x": coordinates[0], "y": coordinates[1]},
                })
                print(f"[OK] Coordenadas {coordinates} guardadas en el json de medida")
            else:
                print("No se han podido obtener las coordenadas, vuelva a intertarlo\n")
        elif selected_mode == 4:
            try:
                scanner = WifiScanner()
            except RuntimeError as e:
                print(f"[ERROR] {e}")
                continue

            # ── Preguntar ráfaga ──
            try:
                n = int(input("¿Cuántas medidas (ráfaga)? [3]: ").strip() or "3")
                interval = float(input("Intervalo entre medidas (s) [1.0]: ").strip() or "1.0")
            except ValueError:
                print("Entrada inválida.")
                continue

            print(f"\n[*] Interfaz: {scanner.interface} | Ráfaga: {n} medidas @ {interval}s\n")
            bursts = scanner.scan_burst(n, interval)

            # ── Guardar cada medida ──
            saved = 0
            for i, scan_result in enumerate(bursts):
                print(f"  [{i+1}/{n}] {scan_result['count']} redes")
                record = session_mgr.create_measurement_record(scan_result)
                res = storage_mgr.save_measurement(
                    session_mgr.config["project_name"], record
                )
                if res["success"]:
                    saved += 1
                else:
                    print(f"  [ERROR] {res['error']}")

            print(f"\n[OK] {saved}/{n} medidas guardadas en data/{session_mgr.config['project_name']}.json")


        elif selected_mode == 5:
            # ── Calibrar m/px ──
            filename = input("Nombre del plano (ej: planta.0.png): ").strip()
            path = os.path.join(BASE_DIR, "img", filename)
            floor = from_filename_get_floor(filename)

            print("Seleccione DOS puntos de referencia en el plano...")
            result = get_two_coordinates_from_map(path, floor)
            if result is None:
                print("No se han seleccionado los dos puntos.")
                continue

            ref1, ref2 = result
            print(f"  Ref 1: {ref1}")
            print(f"  Ref 2: {ref2}")

            try:
                real_m = float(input("Distancia real entre ref1 y ref2 (m): "))
            except ValueError:
                print("Entrada inválida.")
                continue

            m_per_px = calibrate_distance(ref1, ref2, real_m)
            session_mgr.update_tags({"m_per_px": m_per_px})
            print(f"[OK] Escala: {m_per_px:.4f} m/px → guardada en sesión.")
            
        elif selected_mode == 6:
            project = session_mgr.config.get("project_name")
            data_path = os.path.join(BASE_DIR, "data", f"{project}.json")
            try:
                with open(data_path) as f:
                    measurements = json.load(f)
            except FileNotFoundError:
                print(f"No existe {data_path}")
                continue

            # ── Agrupar por prefijo de 5 octetos ──
            connected_aps: dict[str, list[tuple[int, int, float, str]]] = {}
            all_aps: dict[str, int] = {}

            for m in measurements:
                coords = m["conditions"]["coordinates"]
                x, y = coords["x"], coords["y"]
                for n in m["measurement_data"]["networks"]:
                    bssid = n["bssid"].lower()
                    prefix = bssid.rsplit(":", 1)[0]  # 5 octetos
                    all_aps[prefix] = all_aps.get(prefix, 0) + 1
                    if n["connected"]:
                        connected_aps.setdefault(prefix, []).append((x, y, n["signal_dbm"], bssid))

            # ── Lista 1: APs conectados ──
            print(f"\n{'─' * 50}")
            print(f"APs a los que te conectaste ({len(connected_aps)}):")
            print(f"{'─' * 50}")
            for i, (prefix, entries) in enumerate(
                sorted(connected_aps.items(), key=lambda kv: -len(kv[1])), 1
            ):
                rssis = [r for _, _, r, _ in entries]
                bssids = sorted(set(b for *_, b in entries))
                n_pts = len(set((x, y) for x, y, _, _ in entries))
                print(f"  {i}. {prefix}  ({len(entries)} conexiones, "
                        f"{n_pts} pts, RSSI mediana {st.median(rssis):.0f} dBm)")
                print(f"      BSSIDs: {', '.join(bssids)}")

            # ── Lista 2: Todos los APs detectados ──
            print(f"\n{'─' * 50}")
            print(f"Todos los APs detectados ({len(all_aps)}):")
            print(f"{'─' * 50}")
            for i, (prefix, count) in enumerate(
                sorted(all_aps.items(), key=lambda kv: -kv[1]), 1
            ):
                marker = "●" if prefix in connected_aps else "○"
                print(f"  {i}. {marker} {prefix}  ({count} apariciones)")

            print(f"\n→ Copia el prefijo (5 octetos) y usalo en modo 7 u 8.\n")   

        


        elif selected_mode == 7:
            # ── BSSID ──
            target_bssid = input("BSSID del AP a visualizar: ").strip().lower()
            if not target_bssid:
                print("BSSID vacío.")
                continue
            import re
            if not (re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", target_bssid) or
                    re.fullmatch(r"([0-9a-f]{2}:){4}[0-9a-f]{2}", target_bssid)):
                print("Formato inválido. Use aa:bb:cc:dd:ee:ff o aa:bb:cc:dd:ee")
                continue
            # ← CRÍTICO: normalizar SIEMPRE a 5 octetos
            if len(target_bssid) == 17:
                target_bssid = target_bssid.rsplit(":", 1)[0]

            # ── Plano ──
            filename = input("Nombre del plano (ej: planta.0.png): ").strip()
            path = os.path.join(BASE_DIR, "img", filename)
            floor = from_filename_get_floor(filename)

            # ── Coordenadas del AP ──
            print("Seleccione la coordenada del AP en el plano...")
            ap_coords = get_coordinates_from_map(path, floor)
            if ap_coords is None:
                print("No se pudo obtener la coordenada del AP.")
                continue

            # ── Altura ──
            try:
                ap_h = float(input("Altura del AP sobre el suelo (m) [3.0]: ").strip() or "3.0")
                dev_h = float(input("Altura del dispositivo al medir (m) [1.5]: ").strip() or "1.5")
            except ValueError:
                print("Entrada inválida.")
                continue
            height_diff = abs(ap_h - dev_h)

            # ── Escala ──
            m_per_px = session_mgr.config.get("m_per_px")
            if m_per_px is None:
                print("[!] m_per_px no calibrado. Use el modo 5 primero.")
                continue

            # ── Cargar mediciones ──
            project = session_mgr.config.get("project_name")
            data_path = os.path.join(BASE_DIR, "data", f"{project}.json")
            try:
                with open(data_path) as f:
                    measurements = json.load(f)
            except FileNotFoundError:
                print(f"No existe {data_path}")
                continue

            # ── Plot ──
            plot_rssi_on_map(path, floor, measurements, target_bssid, ap_coords, m_per_px, height_diff)   
            
            
        elif selected_mode == 8:

            # ── BSSID ──
            target_bssid = input("BSSID de la antena del AP a visualizar: ").strip().lower()
            if not target_bssid:
                print("BSSID vacío.")
                continue
            import re
            if not re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", target_bssid):
                print("Formato inválido. Use aa:bb:cc:dd:ee:ff")
                continue

            target_bssid_2 = input("BSSID de la misma antena (misma banda) bajo otro SSID [Enter=igual]: ").strip().lower()
            if target_bssid_2 and not re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", target_bssid_2):
                print("Formato inválido.")
                continue
            if not target_bssid_2:
                target_bssid_2 = target_bssid

            # ── Plano ──
            filename = input("Nombre del plano (ej: FIC-P2.png): ").strip()
            path = os.path.join(BASE_DIR, "img", filename)
            floor = from_filename_get_floor(filename)

            # ── Coordenadas del AP ──
            print("Seleccione la coordenada del AP en el plano...")
            ap_coords = get_coordinates_from_map(path, floor)
            if ap_coords is None:
                print("No se pudo obtener la coordenada del AP.")
                continue

            # ── Altura ──
            try:
                ap_h = float(input("Altura del AP sobre el suelo (m) [3.0]: ").strip() or "3.0")
                dev_h = float(input("Altura del dispositivo al medir (m) [1.5]: ").strip() or "1.5")
            except ValueError:
                print("Entrada inválida.")
                continue
            height_diff = abs(ap_h - dev_h)

            # ── Escala ──
            m_per_px = session_mgr.config.get("m_per_px")
            if m_per_px is None:
                print("[!] m_per_px no calibrado. Use el modo 5 primero.")
                continue

            # ── Cargar mediciones ──
            project = session_mgr.config.get("project_name")
            data_path = os.path.join(BASE_DIR, "data", f"{project}.json")
            try:
                with open(data_path) as f:
                    measurements = json.load(f)
            except FileNotFoundError:
                print(f"No existe {data_path}")
                continue

            # ── Recoger observaciones individuales (SOLO mismo plano que el AP) ──
            from collections import defaultdict
            by_point: dict[tuple[int, int], list[float]] = defaultdict(list)
            n_excluidas = 0
            n_nodet = 0  # capturas donde NO se detectó el BSSID

            for m in measurements:
                # Excluir puntos de otras plantas
                if str(m["conditions"].get("floor", "")) != str(floor):
                    n_excluidas += 1
                    continue

                coords = m["conditions"]["coordinates"]
                x, y = coords["x"], coords["y"]
                found = False
                for n in m["measurement_data"]["networks"]:
                    if n["bssid"].lower() == target_bssid or n["bssid"].lower() == target_bssid_2:
                        by_point[(x, y)].append(n["signal_dbm"])
                        found = True
                        break
                if not found:
                    n_nodet += 1

            if not by_point:
                print(f"No hay mediciones para el BSSID {target_bssid} en la planta {floor}.")
                continue

            print(f"\n[*] {len(by_point)} puntos con detección | {n_nodet} capturas sin detección | {n_excluidas} excluidas (otras plantas)")

            # ── Observaciones individuales: cada captura es un punto ──
            data_points = []
            for (x, y), rssis in by_point.items():
                dist = get_distance((x, y), ap_coords, m_per_px, height_diff)
                for r in rssis:
                    data_points.append((dist, r))

            data_points.sort(key=lambda p: p[0])
            distances = [d for d, _ in data_points]
            rssis_plot = [r for _, r in data_points]

            # ── Plot ──
            import numpy as np

            fig, ax = plt.subplots(figsize=(10, 6))

            # Puntos unidos por línea + marcadores
            ax.plot(distances, rssis_plot, "o-", color="steelblue", ms=5,
                    alpha=0.7, linewidth=1, label="Observaciones individuales")

            # Curva teórica: atenuación en espacio libre (1/d²) → RSSI = A - 20·log10(d)
            """d0 = max(min(distances), 0.1)  # distancia mínima (evitar log(0))
            r0 = rssis_plot[distances.index(min(distances))]  # RSSI en d0
            A = r0 + 20 * np.log10(d0)

            d_theory = np.linspace(0.1, max(distances) * 1.1, 200)
            rssi_theory = A - 20 * np.log10(d_theory)

            ax.plot(d_theory, rssi_theory, "r--", lw=1.5,
                    label=f"Teórica (1/d²): {A:.1f} − 20·log₁₀(d)")"""

            ax.set_xlabel("Distancia al AP (m)", fontsize=12)
            ax.set_ylabel("RSSI (dBm)", fontsize=12)
            ax.set_title(
                f"RSSI vs Distancia — BSSID: {target_bssid}\n"
                f"Planta {floor} | {len(data_points)} obs. en {len(by_point)} puntos | "
                f"{n_nodet} no-detecciones",
                fontsize=12
            )
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=10)
            plt.tight_layout()
            fig.savefig("grafica.png", dpi=150, bbox_inches="tight")

            plt.show()
            
        elif selected_mode == 9:
            project = session_mgr.config.get("project_name")
            data_path = os.path.join(BASE_DIR, "data", f"{project}.json")
            try:
                with open(data_path) as f:
                    measurements = json.load(f)
            except FileNotFoundError:
                print(f"No existe {data_path}")
                continue

            # ── Extraer puntos únicos con capturas ──
            from collections import defaultdict
            points_with_data: dict[tuple[int, int], int] = defaultdict(int)
            for m in measurements:
                c = m["conditions"]["coordinates"]
                if c.get("x") is not None and c.get("y") is not None:
                    points_with_data[(c["x"], c["y"])] += 1

            if not points_with_data:
                print("No hay capturas con coordenadas.")
                continue

            # ── Mostrar lista numerada ──
            sorted_points = sorted(points_with_data.keys())
            print(f"\n{'─' * 40}")
            print(f"Puntos con medidas ({len(sorted_points)}):")
            print(f"{'─' * 40}")
            for i, (x, y) in enumerate(sorted_points, 1):
                n = points_with_data[(x, y)]
                print(f"  {i}. ({x}, {y}) — {n} capturas")
            print(f"{'─' * 40}")

            # ── Seleccionar por número ──
            try:
                choice = int(input(f"Selecciona un punto [1-{len(sorted_points)}]: "))
            except ValueError:
                print("Entrada inválida.")
                continue
            if choice < 1 or choice > len(sorted_points):
                print("Opción fuera de rango.")
                continue

            x_pt, y_pt = sorted_points[choice - 1]
            n_capturas = points_with_data[(x_pt, y_pt)]
            print(f"[*] Punto ({x_pt}, {y_pt}) — {n_capturas} capturas")

            # ── Filtrar capturas en ese punto ──
            sel = [m for m in measurements
                   if m["conditions"]["coordinates"].get("x") == x_pt
                   and m["conditions"]["coordinates"].get("y") == y_pt]

            # ── Info general ──
            equipos = set()
            fechas = []
            for m in sel:
                h = m["conditions"].get("device", {}).get("hostname")
                if h:
                    equipos.add(h)
                t = m.get("timestamp")
                if t:
                    fechas.append(t)

            print(f"    Equipo: {', '.join(equipos) if equipos else 'N/A'}")
            if fechas:
                fechas.sort()
                print(f"    Rango temporal: {fechas[0][:19]} → {fechas[-1][:19]}")

            # ── Agrupar por BSSID ──
            ap_data: dict[str, dict] = defaultdict(lambda: {
                "ssid": "", "det": 0, "conn": 0,
                "rssis": [], "freqs": [], "channels": [],
                "standard": ""
            })

            for m in sel:
                for n in m["measurement_data"]["networks"]:
                    b = n.get("bssid")
                    if not b:
                        continue
                    b = b.lower()
                    d = ap_data[b]
                    d["ssid"] = n.get("ssid", "") or ""
                    d["det"] += 1
                    if n.get("connected"):
                        d["conn"] += 1
                    if n.get("signal_dbm") is not None:
                        d["rssis"].append(n["signal_dbm"])
                    if n.get("frequency_mhz") is not None:
                        d["freqs"].append(n["frequency_mhz"])
                    if n.get("channel") is not None:
                        d["channels"].append(n["channel"])
                    d["standard"] = n.get("standard", "") or ""

            # ── Imprimir tabla ──
            print(f"\n{'═' * 110}")
            print(f"Tabla de BSSIDs en punto ({x_pt}, {y_pt}) | {n_capturas} capturas")
            print(f"{'═' * 110}")
            print(f"{'BSSID':<18} {'SSID':<16} {'Det':>4} {'Conn':>5} {'Med(dBm)':>9} {'n':>4} {'Freq(MHz)':>10} {'Canal':>6} {'Banda':>6} {'Std':<10}")
            print(f"{'─' * 110}")

            for bssid, d in sorted(ap_data.items(), key=lambda kv: -kv[1]["det"]):
                med_str = f"{st.median(d['rssis']):>9.0f}" if d["rssis"] else f"{'N/A':>9}"
                freq = d["freqs"][0] if d["freqs"] else None
                chan = d["channels"][0] if d["channels"] else None
                freq_str = f"{freq:>10}" if freq is not None else f"{'N/A':>10}"
                chan_str = f"{chan:>6}" if chan is not None else f"{'N/A':>6}"
                if freq is not None:
                    banda = "2.4" if freq < 3000 else ("5" if freq < 6000 else "6")
                else:
                    banda = "N/A"
                ssid = d["ssid"][:17] if d["ssid"] else "-"   
                std = d["standard"][:9] if d["standard"] else "-"
                print(f"{bssid:<18} {ssid:<16} {d['det']:>4} {d['conn']:>5} {med_str} {len(d['rssis']):>4} {freq_str} {chan_str} {banda:>6} {std:<10}")

            print(f"{'─' * 110}")
            print(f"Med = mediana en dBm | n = nº obs. válidas | Det = capturas donde aparece | Conn = capturas con conexión")
            print(f"{'═' * 110}\n")

            # ── Resumen ──
            n_bssids = len(ap_data)
            conectados = {b: d for b, d in ap_data.items() if d["conn"] > 0}

            # Solo BSSIDs con al menos una lectura de RSSI para comparar
            with_rssi = {b: d for b, d in ap_data.items() if d["rssis"]}
            top_senal = max(with_rssi.items(), key=lambda kv: st.median(kv[1]["rssis"])) if with_rssi else None
            top_freq = max(ap_data.items(), key=lambda kv: kv[1]["det"])

            print(f"Resumen:")
            print(f"  • {n_bssids} BSSIDs distintos detectados")
            if top_senal:
                print(f"  • Mayor nivel de señal: {top_senal[0]} (mediana {st.median(top_senal[1]['rssis']):.0f} dBm)")
            else:
                print(f"  • Mayor nivel de señal: N/A (sin lecturas de RSSI)")
            #print(f"  • Más frecuente: {top_freq[0]} ({top_freq[1]['det']} detecciones de {n_capturas})"
            if conectados:
                print(f"  • Con conexión ({len(conectados)}):")
                for b, d in conectados.items():
                    print(f"      {b} — {d['conn']}/{n_capturas} capturas conectadas")
            else:
                print(f"  • Ningún BSSID con conexión en este punto")
            print()     
                    


if __name__ == "__main__":
    cli()