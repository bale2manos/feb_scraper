import matplotlib.pyplot as plt
import pandas as pd
import requests
import os
from PIL import Image
from io import BytesIO
from utils import setup_montserrat_font, MIN_PARTIDOS

def get_image_from_url(url, size=(80, 80)):
    try:
        from rembg import remove
        if (not url or str(url).strip() == '' or str(url).lower() == 'nan' or str(url) == 'images/templates/generic_player.png'):
            # Imagen genérica de jugador
            generic_path = os.path.join(os.path.dirname(__file__), '../images/templates/generic_player.png')
            if os.path.exists(generic_path):
                img = Image.open(generic_path).convert('RGBA')
            else:
                img = Image.new('RGBA', size, (220,220,220,255))
            return img
        try:
            response = requests.get(url)
            img = Image.open(BytesIO(response.content)).convert('RGBA')
        except Exception:
            # Si la URL no devuelve imagen válida, usar genérica
            generic_path = os.path.join(os.path.dirname(__file__), '../../images/templates/generic_player.png')
            if os.path.exists(generic_path):
                img = Image.open(generic_path).convert('RGBA')
            else:
                img = Image.new('RGBA', size, (220,220,220,255))
            return img
        # Mantener proporciones originales, ajustar solo si es demasiado grande
        max_width, max_height = size
        w, h = img.size
        scale = min(max_width/w, max_height/h, 1.0)
        new_size = (int(w*scale), int(h*scale))
        img = img.resize(new_size, Image.LANCZOS)
        img_no_bg = remove(img)
        return img_no_bg
    except Exception:
        # Imagen de fallback si no se puede cargar
        return Image.new('RGBA', size, (220,220,220,0))

def plot_top_turnovers(
df: pd.DataFrame,
equipo: str,
figsize: tuple = (4, 3.5),
min_games: int = None
) -> plt.Figure:
    """
    Genera una figura con los 4 jugadores que más pérdidas cometen de media (mínimo partidos configurables) para un equipo.
    Muestra: Imagen pequeña, Dorsal, Nombre, Perdidas/PJ
    """
    setup_montserrat_font()
    
    # Use parameter min_games if provided, otherwise use MIN_PARTIDOS constant
    min_partidos = min_games if min_games is not None else MIN_PARTIDOS
    
    # Filtrar jugadores del equipo con al menos el mínimo de partidos especificado
    df_team = df[(df['EQUIPO'] == equipo) & (df['PJ'] >= min_partidos)].copy()
    # PERDIDAS ya viene ponderada (promedio por partido) en el archivo aggregated
    df_team['TOV_PJ'] = df_team['PERDIDAS']
    top = df_team.sort_values('TOV_PJ', ascending=False).head(4)

    # Calcular el ancho necesario para el nombre más largo
    max_name = top['JUGADOR'].astype(str).map(len).max()
    # Estimar ancho: base + ancho por caracter
    base_width = 5
    extra_width = max(0, (max_name-15)*0.25)
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111)
    ax.axis('off')

    # Layout vertical
    card_height = 1.0 / (len(top) + 0.3)
    y_start = 1.0 - card_height / 2
    # Espacio fijo entre dorsal y nombre
    space_x = 0.10  # Más margen entre dorsal y nombre
    for i, row in enumerate(top.itertuples()):
        y = y_start - i * card_height
        # Imagen (sin fondo), tamaño fijo en alto, respetando proporción original
        img = get_image_from_url(getattr(row, 'IMAGEN', ''))
        img_w, img_h = img.size
        img_h_axes = card_height * 0.7  # Más pequeño para dejar espacio a texto
        img_w_axes = img_h_axes * (img_w / img_h)
        x0 = 0.02
        x1 = x0 + img_w_axes
        y0 = y - img_h_axes/2
        y1 = y + img_h_axes/2
        ax.imshow(img, extent=(x0, x1, y0, y1), aspect='auto', zorder=2)
        # Dorsal y nombre en la misma línea, a la derecha de la imagen
        dorsal_x = x1 + 0.01
        name_x = dorsal_x + space_x
        ax.text(dorsal_x, y+0.01, f"{getattr(row, 'DORSAL', '')}", fontsize=13, weight='bold', color='#4169E1', va='center', ha='left', fontfamily='Montserrat')
        ax.text(name_x, y+0.01, getattr(row, 'JUGADOR', ''), fontsize=11, weight='bold', color='#222', va='center', ha='left', fontfamily='Montserrat')
        # T3% en letra pequeña debajo
        ax.text(dorsal_x, y-0.04, f"{getattr(row, 'TOV_PJ', 0):.1f} pérdidas", fontsize=10, weight='bold', color='#2E8B57', va='top', ha='left', fontfamily='Montserrat')
        # Línea separadora
        if i < 3:
            ax.plot([0.12,0.88],[y-card_height/2, y-card_height/2], color='#eee', lw=2, zorder=1)
    ax.set_xlim(0,1)
    ax.set_ylim(0,1)
    plt.tight_layout(pad=0.2)
    return fig

if __name__ == "__main__":
    FILE = './data/jugadores_aggregated_24_25.xlsx'
    EQUIPO = "UROS DE RIVAS"
    df = pd.read_excel(FILE)
    fig = plot_top_turnovers(df, EQUIPO)
    fig.savefig('top_turnovers_test.png', dpi=180, bbox_inches='tight')
    print("Gráfico de máximos perdedores guardado como 'top_turnovers_test.png'")
