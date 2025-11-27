from scraper_live import scrape_boxscore_live
from normalizer import normalize_game_data
from stats_engine import analyze_game
from presentation_text import generate_text_report, presentation_pdf
from utils.web_scraping import init_driver

driver = init_driver()
data = scrape_boxscore_live(driver, "2487620")
driver.quit()
print(data)
norm = normalize_game_data(data)
analysis = analyze_game(norm)

print(generate_text_report(analysis))
# Generar el PDF
pdf_path = presentation_pdf(analysis)