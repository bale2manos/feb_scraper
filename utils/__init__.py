import os
from PIL import Image


def get_team_logo(team_name: str):
    """Load team logo image from images/clubs/ directory."""
    fn = (team_name.lower()
               .replace(' ', '_')
               .replace('.', '')
               .replace(',', '')
               .replace('á', 'a')
               .replace('é', 'e')
               .replace('í', 'i')
               .replace('ó', 'o')
               .replace('ú', 'u')
               .replace('ñ', 'n')
               .replace('ü', 'u'))
    path = os.path.join(
        os.path.dirname(__file__),
        '..', 'images', 'clubs',
        f'{fn}.png'
    )
    if os.path.exists(path):
        return Image.open(path).convert('RGBA')
    else:
        print(f"⚠️ Logo not found for team: {team_name} (looking for {path})")
    return None


def setup_montserrat_font():
    """Setup Montserrat font for matplotlib."""
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from pathlib import Path
    
    # Path to fonts directory
    font_dir = Path(__file__).parent.parent / "fonts"
    
    # Register Montserrat fonts
    font_files = [
        "Montserrat-Regular.ttf",
        "Montserrat-Bold.ttf", 
        "Montserrat-Medium.ttf",
        "Montserrat-SemiBold.ttf"
    ]
    
    for font_file in font_files:
        font_path = font_dir / font_file
        if font_path.exists():
            try:
                fm.fontManager.addfont(str(font_path))
            except Exception as e:
                print(f"Warning: Could not register font {font_file}: {e}")
    
    # Set Montserrat as default font family
    plt.rcParams['font.family'] = 'Montserrat'


# Import common constants
try:
    from config import MIN_PARTIDOS
except ImportError:
    MIN_PARTIDOS = 5  # Default value