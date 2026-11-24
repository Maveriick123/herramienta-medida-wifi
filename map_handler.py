import os
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import math
import statistics as st
from collections import namedtuple

def calibrate_distance(ref1: tuple[int, int], ref2: tuple[int, int], real_m: float) -> float:
    """Devuelve m/píxel a partir de dos puntos de referencia y su distancia real."""
    dist_px = math.hypot(ref2[0] - ref1[0], ref2[1] - ref1[1])
    if dist_px == 0:
        raise ValueError("Los dos puntos de referencia son idénticos.")
    return real_m / dist_px

def get_distance(
    p1: tuple[int, int],
    p2: tuple[int, int],
    m_per_px: float,
    height_diff: float = 0.0,   # ← nueva: |z_AP − z_dispositivo| en metros
) -> float:
    """Devuelve la distancia real (m) entre dos puntos del plano + diferencia vertical."""
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1], height_diff) * m_per_px   


def get_two_coordinates_from_map(path: str, floor: int) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Abre el plano y permite seleccionar DOS puntos (clic 1 y clic 2)."""
    try:
        img = mpimg.imread(path)
    except:
        print(f"map_handler.py: Image not found in: {path}")
        return None

    fig, ax = plt.subplots(figsize=(14, 10))
    ax.imshow(img, origin='upper')
    ax.set_title(f"Floor: {floor} — clic 1: ref1 | clic 2: ref2 | ESC para cancelar")

    coordinates = []

    def on_click(event):
        if event.inaxes == ax and event.button == 1:
            coordinates.append((int(round(event.xdata)), int(round(event.ydata))))
            ax.plot(*coordinates[-1], marker="x", color="red", markersize=12,
                    markeredgewidth=2, zorder=6)
            if len(coordinates) == 2:
                plt.close(fig)

    def on_key(event):
        if event.key == "escape":
            plt.close(fig)

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.show()

    if len(coordinates) == 2:
        return coordinates[0], coordinates[1]
    return None   

def from_filename_get_floor(filename:str) -> int:
    # rsplit para que corte desde la derecha, sólo una vez (ver parámetros)
    # Así si el nombre tiene puntos internos funcionará igual
    # Cogemos solo el nombre:
    # I.e: planta.1.png --> ["planta.1", "png"]
    raw_name = filename.rsplit(".", 1)[0]
    digits:str = ""
    for ch in reversed(raw_name):
        if ch.isdigit():
            digits = ch + digits
        else:
            break
    if not digits:
        raise ValueError("map_handler.py: No se especifica la planta en el nombre del plano(obligatorio)\n")
    else:
        return int(digits)

def get_coordinates_from_map(path: str, floor: int) -> tuple[int, int] | None:
    try:
        img = mpimg.imread(path)
    except:
        print(f"map_handler.py: Image not found in: {path}")
        return None

    fig, ax = plt.subplots(figsize=(14, 10))
    ax.imshow(img, origin='upper')
    ax.set_title(f"Floor: {floor} — clic para seleccionar, ESC para cancelar")

    coordinates = []

    def on_click(event):
        if event.inaxes == ax and event.button == 1:
            coordinates.append((int(round(event.xdata)), int(round(event.ydata))))
            plt.close(fig)   

    def on_key(event):
        if event.key == "escape":
            plt.close(fig)

    # fig.canvas --> backend gráfico, la ventana donde vive la img
    # .mpl_connect --> asocia el evento con el callback
    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.show() # Hasta que se cierre la ventana no continua la ejecución

    return coordinates[0] if coordinates else None   


"""def plot_rssi_on_map(
    path: str,
    floor: int,
    measurements: list[dict],
    target_bssid: str,
    ap_coords: tuple[int, int],
    m_per_px: float,
    height_diff: float = 0.0,
):
    
    #Plotea el RSSI del AP (por prefijo de 5 octetos) en cada punto de medición.
    #Agrupa todas las radios/SSIDs del mismo AP físico cogiendo todos los bssids distintos que #emite.
    
    from collections import defaultdict

    try:
        img = mpimg.imread(path)
    except:
        print(f"map_handler.py: Image not found in: {path}")
        return

    # Filtramos por los 5 primeros octetos
    # rsplit(":", 1) --> Separa a partir del último punto y coma empezando desde el final (reverse split)
    prefix = ":".join(target_bssid.lower().split(":")[:5])

    # ── Filtrar por prefijo y agrupar por (x, y) ──
    by_point = defaultdict(list)
    # measurements se pasa por parámtro y contiene los datos del json que contiene las mediciones...
    for m in measurements:
        # Tipar c, que es ¿?
        c = m["conditions"]["coordinates"]
        # Campo measurement_data y accedes al campo networ
        # El campo network es una lista con las redes detectadas por la NIC

        # Primero: ¿a qué red está conectado en esta medición?
        conn_bssid = conn_rssi = conn_freq = None
        for n in m["measurement_data"]["networks"]:
            if n["connected"]:
                conn_bssid = n["bssid"]
                conn_rssi = n["signal_dbm"]
                conn_freq = n["frequency_mhz"]
                break

        # Segundo: buscar el AP objetivo
        for n in m["measurement_data"]["networks"]:
            # Guardamos la info del bssid al que esta conectado el equipo en esta medición
            # Si no es el app objetivo le añadiremos la información a mayor, para pintar
            # en el evento onClick()
            if n["bssid"].lower().rsplit(":", 1)[0] == prefix:
                is_connected_to_target_ap = n["connected"]
                # Vemos si el AP objetivo es al que estamos conectado...
                if is_connected_to_target_ap:
                    by_point[(c["x"], c["y"])].append((n["signal_dbm"], n["connected"], n["bssid"], n["frequency_mhz"], None, None, None))
                else:
                    by_point[(c["x"], c["y"])].append((n["signal_dbm"], n["connected"], n["bssid"], n["frequency_mhz"], conn_bssid, conn_rssi, conn_freq))

    if not by_point:
        print(f"No hay mediciones para el AP con algún bssid tal que coincida con {prefix}:*")
        return

    # ── Un punto por coordenada ──
    # (x, y, median_rssi, any_connected, n, min_rssi, max_rssi)
    points = []
    # Pattern matching
    # (3,4),[medicion1:tupla, medicion2:tupla] en el diccionario de listas
    # (signal_dbm, connected, bssid, frequency, connected_bssid, conected_rssi, connected_frequency)
    for (x, y), vals in by_point.items():
        # [x for x in iterable] + patternmatching
        # Coges del punto el primer valor, el resto _ los ignoras...
        rssis = [r for r, _, _, _, _, _, _ in vals]
        # En ese punto se conecto alguna vez...
        # Buscar la primera medición donde connected=True (si existe)
        connected_entry = next(((b, f) for _, c, b, f, _, _, _ in vals if c), (None, None))
        bssid, frequency = connected_entry
        connected = bssid is not None

        # Si está conectado, la mediana para el color es solo de la banda conectada
        # Si no está conectado, la mediana es de todas las bandas
        if connected:
            rssis_for_color = [r for r, c, _, _, _, _, _ in vals if c]
        else:
            rssis_for_color = [r for r, _, _, f, _, _, _ in vals if 5000 <= f < 6000]

        median_rssi = st.median(rssis_for_color)
        max_rssi = max(rssis_for_color)
        min_rssi = min(rssis_for_color)

        # Mediana por banda (siempre, para el tooltip)
        bands = {"2.4": [], "5": [], "6": []}
        for r, _, _, f, _, _, _ in vals:
            if f < 3000:
                bands["2.4"].append(r)
            elif f < 6000:
                bands["5"].append(r)
            else:
                bands["6"].append(r)
        band_medians = {k: st.median(v) for k, v in bands.items() if v}

        # Ver si en ese punto se detecto el ap objetivo pero no se conecto el equipo a él
        
        #if not connected:
            #connected_bssids_not_target, connected_rssi_not_target, #connected_frequency_not_target = [(b, r, f) for _, c, _,b,r,f in vals if c]
        

        Info = namedtuple('Bssid', ['bssid', 'rssi', 'frequency'])
        list_not_connected_target_ap: list[Info] = []

        seen = set()
        for current_med in vals:
            # También conected igual a false serviría...
            if current_med[4] != None:
                key = current_med[4]  # solo el BSSID
                if key not in seen:
                    seen.add(key)
                    list_not_connected_target_ap.append(Info(key, current_med[5], current_med[6]))

        points.append((x, y, bssid, median_rssi, min_rssi, max_rssi, frequency, connected, list_not_connected_target_ap, band_medians))

    # ── Color por RSSI ──
    def rssi_color(rssi: float) -> str:
        if rssi >= -50: return "green"
        if rssi >= -65: return "yellow"
        if rssi >= -75: return "orange"
        return "red"

    # ── Plot ──
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.imshow(img, origin='upper')
    ax.set_title(f"Floor: {floor} — RSSI de AP con BSSID de la forma {prefix}:*\n"
                 f"Clic sobre un punto para ver detalles | ESC para cerrar", fontsize=11)

    # AP
    ax.plot(*ap_coords, marker="^", color="blue", markersize=14,
            markeredgecolor="black", markeredgewidth=1, zorder=6)
    ax.annotate("AP", xy=ap_coords, xytext=(ap_coords[0]+15, ap_coords[1]+15),
                fontsize=9, color="blue", fontweight="bold")

    # Puntos de medición
    for x, y, bssid, median_rssi, min_rssi, max_rssi, frequency, connected, list_not_connected_target_ap, band_medians in points:

        ax.plot(x, y,
                marker="o" if connected else "s",
                color=rssi_color(max_rssi),
                markersize=11,
                markeredgecolor="black",
                markeredgewidth=0.8,
                zorder=5)

    # Leyenda
    # Revisar...
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="^", color="w", markerfacecolor="blue",
               markeredgecolor="black", markersize=12, label="AP"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="green",
               markeredgecolor="black", markersize=10, label="<= -50 dBm"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="yellow",
               markeredgecolor="black", markersize=10, label="-50 a -65 dBm"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="orange",
               markeredgecolor="black", markersize=10, label="-65 a -75 dBm"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="red",
               markeredgecolor="black", markersize=10, label=">= -75 dBm"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="gray",
               markeredgecolor="black", markersize=10, label="Conectado"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="gray",
               markeredgecolor="black", markersize=10, label="No conectado"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9, framealpha=0.8)

    # ── Interactividad ──
    current_ann = [None]

    # Adaptar el onClick()...
    def on_click(event):
        if event.inaxes != ax or event.button != 1:
            return
        best, best_d = None, 20
        for p in points:
            d = math.hypot(p[0] - event.xdata, p[1] - event.ydata)
            if d < best_d:
                best_d, best = d, p
        if current_ann[0]:
            current_ann[0].remove()
            current_ann[0] = None
        if best:
            x, y, bssid, median_rssi, rssi_min, rssi_max, frequency, connected, list_not_connected_target_ap, band_medians = best
            dist = get_distance((x, y), ap_coords, m_per_px, height_diff)

            lines = []
            if connected:
                lines.append(f"Mediana del RSSI al AP objetivo en la banda conectada: {median_rssi:.0f} dBm")
                lines.append(f"✓ Conectado en la banda de {frequency/1000:.1f} GHz con BSSID asociado {bssid}")
            else:
                lines.append("✗ No conectado")
                # Mediana por banda (sustituye a la mediana global)
                for band_name, med in band_medians.items():
                    lines.append(f"  {band_name} GHz: {med:.0f} dBm")
            lines.append(f"Distancia al AP: {dist:.1f} m")

            if not connected and list_not_connected_target_ap:
                lines.append("Conectado a BSSID no perteneciente al AP objetivo:")
                for i in list_not_connected_target_ap:
                    lines.append(f"  {i.bssid} | {i.rssi:.0f} dBm | {i.frequency/1000:.1f} GHz")
            text = "\n".join(lines)   

            current_ann[0] = ax.annotate(
                text, xy=(x, y), xytext=(x+30, y-40),
                fontsize=10, color="white",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="black", alpha=0.85),
                arrowprops=dict(arrowstyle="->", color="white", lw=1.2),
                zorder=10)
            fig.canvas.draw_idle()

    def on_key(event):
        if event.key == "escape":
            plt.close(fig)

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.show()   """
    
def plot_rssi_on_map(
    path: str,
    floor: int,
    measurements: list[dict],
    target_bssid: str,
    ap_coords: tuple[int, int],
    m_per_px: float,
    height_diff: float = 0.0,
    ):
    """
    Plotea el RSSI del AP (por prefijo de 5 octetos) en cada punto de medición.
    Agrupa todas las radios/SSIDs del mismo AP físico cogiendo todos los bssids distintos que emite.
    """
    from collections import defaultdict

    try:
        img = mpimg.imread(path)
    except:
        print(f"map_handler.py: Image not found in: {path}")
        return

    # Filtramos por los 5 primeros octetos
    # rsplit(":", 1) --> Separa a partir del último punto y coma empezando desde el final (reverse split)
    prefix = ":".join(target_bssid.lower().split(":")[:5])

    # ── Filtrar por prefijo y agrupar por (x, y) ──
    # SOLO puntos del mismo plano (edificio y planta) que el AP
    by_point = defaultdict(list)
    # measurements se pasa por parámtro y contiene los datos del json que contiene las mediciones...
    n_excluidas = 0
    for m in measurements:
        # Excluir puntos de otras plantas
        if str(m["conditions"].get("floor", "")) != str(floor):
            n_excluidas += 1
            continue

        # Tipar c, que es ¿?
        c = m["conditions"]["coordinates"]
        # Campo measurement_data y accedes al campo networ
        # El campo network es una lista con las redes detectadas por la NIC

        # Primero: ¿a qué red está conectado en esta medición?
        conn_bssid = conn_rssi = conn_freq = None
        for n in m["measurement_data"]["networks"]:
            if n["connected"]:
                conn_bssid = n["bssid"]
                conn_rssi = n["signal_dbm"]
                conn_freq = n["frequency_mhz"]
                break

        # Segundo: buscar el AP objetivo
        for n in m["measurement_data"]["networks"]:
            # Guardamos la info del bssid al que esta conectado el equipo en esta medición
            # Si no es el app objetivo le añadiremos la información a mayor, para pintar
            # en el evento onClick()
            if n["bssid"].lower().rsplit(":", 1)[0] == prefix:
                is_connected_to_target_ap = n["connected"]
                # Vemos si el AP objetivo es al que estamos conectado...
                if is_connected_to_target_ap:
                    by_point[(c["x"], c["y"])].append((n["signal_dbm"], n["connected"], n["bssid"], n["frequency_mhz"], None, None, None))
                else:
                    by_point[(c["x"], c["y"])].append((n["signal_dbm"], n["connected"], n["bssid"], n["frequency_mhz"], conn_bssid, conn_rssi, conn_freq))

    if not by_point:
        print(f"No hay mediciones para el AP con algún bssid tal que coincida con {prefix}:*")
        return

    if n_excluidas:
        print(f"[i] {n_excluidas} capturas excluidas (otras plantas).")

    # ── Un punto por coordenada ──
    # (x, y, median_rssi, any_connected, n, min_rssi, max_rssi)
    points = []
    # Pattern matching
    # (3,4),[medicion1:tupla, medicion2:tupla] en el diccionario de listas
    # (signal_dbm, connected, bssid, frequency, connected_bssid, conected_rssi, connected_frequency)
    for (x, y), vals in by_point.items():
        # [x for x in iterable] + patternmatching
        # Coges del punto el primer valor, el resto _ los ignoras...
        rssis = [r for r, _, _, _, _, _, _ in vals]
        # En ese punto se conecto alguna vez...
        # Buscar la primera medición donde connected=True (si existe)
        connected_entry = next(((b, f) for _, c, b, f, _, _, _ in vals if c), (None, None))
        bssid, frequency = connected_entry
        connected = bssid is not None

        # Si está conectado, la mediana para el color es solo de la banda conectada
        # Si no está conectado, la mediana es de todas las bandas
        if connected:
            rssis_for_color = [r for r, c, _, _, _, _, _ in vals if c]
        else:
            rssis_for_color = [r for r, _, _, f, _, _, _ in vals if 5000 <= f < 6000]
            if not rssis_for_color:
                rssis_for_color = rssis

        # ← LA PRÁCTICA PIDE MEDIANA PARA EL COLOR
        median_rssi = st.median(rssis_for_color)
        max_rssi = max(rssis_for_color)
        min_rssi = min(rssis_for_color)

        # Mediana por banda (siempre, para el tooltip)
        bands = {"2.4": [], "5": [], "6": []}
        for r, _, _, f, _, _, _ in vals:
            if f < 3000:
                bands["2.4"].append(r)
            elif f < 6000:
                bands["5"].append(r)
            else:
                bands["6"].append(r)
        band_medians = {k: st.median(v) for k, v in bands.items() if v}

        # Ver si en ese punto se detecto el ap objetivo pero no se conecto el equipo a él
        """
        if not connected:
            connected_bssids_not_target, connected_rssi_not_target, connected_frequency_not_target = [(b, r, f) for _, c, _,b,r,f in vals if c]
        """

        Info = namedtuple('Bssid', ['bssid', 'rssi', 'frequency'])
        list_not_connected_target_ap: list[Info] = []

        seen = set()
        for current_med in vals:
            # También conected igual a false serviría...
            if current_med[4] != None:
                key = current_med[4]  # solo el BSSID
                if key not in seen:
                    seen.add(key)
                    list_not_connected_target_ap.append(Info(key, current_med[5], current_med[6]))

        points.append((x, y, bssid, median_rssi, min_rssi, max_rssi, frequency, connected, list_not_connected_target_ap, band_medians))

    # ── Color por RSSI (continuo para colorbar) ──
    # La práctica pide barra de color con escala numérica
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    import numpy as np

    # Rango típico de RSSI WiFi: -90 a -30 dBm
    norm = mcolors.Normalize(vmin=-90, vmax=-30)
    cmap = cm.RdYlGn  # rojo (mala) → verde (buena)

    # ── Plot ──
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.imshow(img, origin='upper')
    ax.set_title(f"Floor: {floor} — RSSI de AP con BSSID de la forma {prefix}:*\n"
                 f"Clic sobre un punto para ver detalles | ESC para cerrar", fontsize=11)

    # AP
    ax.plot(*ap_coords, marker="^", color="blue", markersize=14,
            markeredgecolor="black", markeredgewidth=1, zorder=6)
    ax.annotate("AP", xy=ap_coords, xytext=(ap_coords[0]+15, ap_coords[1]+15),
                fontsize=9, color="blue", fontweight="bold")

    # Puntos de medición — coloreados por MEDIANA
    for x, y, bssid, median_rssi, min_rssi, max_rssi, frequency, connected, list_not_connected_target_ap, band_medians in points:
        color = cmap(norm(median_rssi))
        ax.plot(x, y,
                marker="o" if connected else "s",
                color=color,
                markersize=11,
                markeredgecolor="black",
                markeredgewidth=0.8,
                zorder=5)

    # ← BARRA DE COLOR (colorbar) con escala numérica
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, orientation="horizontal", pad=0.08, shrink=0.8)   
    cbar.set_label("RSSI mediana (dBm)", fontsize=10)

    # Leyenda
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0],[0], marker="^", color="w", markerfacecolor="blue",
               markeredgecolor="black", markersize=12, label="AP"),
        Line2D([0],[0], marker="o", color="w", markerfacecolor="gray",
               markeredgecolor="black", markersize=10, label="Conectado"),
        Line2D([0],[0], marker="s", color="w", markerfacecolor="gray",
               markeredgecolor="black", markersize=10, label="No conectado"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9, framealpha=0.8)

    # ── Interactividad ──
    current_ann = [None]

    # Adaptar el onClick()...
    def on_click(event):
        if event.inaxes != ax or event.button != 1:
            return
        best, best_d = None, 20
        for p in points:
            d = math.hypot(p[0] - event.xdata, p[1] - event.ydata)
            if d < best_d:
                best_d, best = d, p
        if current_ann[0]:
            current_ann[0].remove()
            current_ann[0] = None
        if best:
            x, y, bssid, median_rssi, rssi_min, rssi_max, frequency, connected, list_not_connected_target_ap, band_medians = best
            dist = get_distance((x, y), ap_coords, m_per_px, height_diff)

            lines = []
            if connected:
                lines.append(f"Mediana del RSSI al AP objetivo en la banda conectada: {median_rssi:.0f} dBm")
                lines.append(f"✓ Conectado en la banda de {frequency/1000:.1f} GHz con BSSID asociado {bssid}")
            else:
                lines.append("✗ No conectado")
                # Mediana por banda (sustituye a la mediana global)
                for band_name, med in band_medians.items():
                    lines.append(f"  {band_name} GHz: {med:.0f} dBm")
            lines.append(f"Distancia al AP: {dist:.1f} m")

            if not connected and list_not_connected_target_ap:
                lines.append("Conectado a BSSID no perteneciente al AP objetivo:")
                for i in list_not_connected_target_ap:
                    lines.append(f"  {i.bssid} | {i.rssi:.0f} dBm | {i.frequency/1000:.1f} GHz")
            text = "\n".join(lines)

            xdata_lim = ax.get_xlim()[1]
            ydata_lim = ax.get_ylim()[0]
            dx = 30 if x + 30 < xdata_lim else -120
            dy = -40 if y - 40 > ydata_lim else 40

            current_ann[0] = ax.annotate(
                text, xy=(x, y), xytext=(x + dx, y + dy),
                fontsize=10, color="white",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="black", alpha=0.85),
                arrowprops=dict(arrowstyle="->", color="white", lw=1.2),
                zorder=10,
                annotation_clip=False)
            fig.canvas.draw_idle()

    def on_key(event):
        if event.key == "escape":
            plt.close(fig)

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    ##fig.savefig("plano_rssi.png", dpi=150, bbox_inches="tight")
    plt.show()   