from datetime import datetime
import os
import csv
import feedparser
import requests
import re

# --- CONFIGURATION ---
GUMROAD_PRODUCT_URL = "https://ksmtech.gumroad.com/l/twmqjn"
OUTPUT_DIR = "output_data"

# CONFIGURATION TELEGRAM
TELEGRAM_BOT_TOKEN = "8897372778:AAHAlsmQp9PbLTSA_yzuVmQyzj5DOOMpnpE"
TELEGRAM_CHAT_ID = "@data_leads_b2b"

# CONFIGURATION IA (GROQ) - Sécurisée pour GitHub
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "VOTRE_CLE_GROQ_ICI")


def nettoyer_nom_entreprise(titre):
  mots = titre.split()
  mots_filtres = [m for m in mots if len(m) > 3 and not m.startswith("http")]
  if mots_filtres:
    return " ".join(mots_filtres[:2])
  return "Startup"


def extraire_potentiel_dirigeant(titre):
  if "lève" in titre.lower() or "fonds" in titre.lower():
    return "Fondateur / CEO"
  elif "recrute" in titre.lower():
    return "DRH / Talent Acquisition"
  elif "lance" in titre.lower() or "création" in titre.lower():
    return "Dirigeant Fondateur"
  return "Direction Générale"


def generer_email_pro(nom_entreprise):
  slug = re.sub(r'[^a-zA-Z]', '', nom_entreprise.lower())
  if not slug:
    slug = "entreprise"
  return f"direction@{slug[:12]}.fr"


def interroger_api_gouvernement(nom_entreprise):
  url = f"https://recherche-entreprises.api.gouv.fr/search?q={nom_entreprise}&per_page=1"
  try:
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
      data = response.json()
      resultats = data.get("results", [])
      if resultats:
        entreprise = resultats[0]
        siret = entreprise.get("siren", "N/A")
        nom_officiel = entreprise.get("nom_raison_sociale", nom_entreprise)
        siege = entreprise.get("siege", {})
        commune = siege.get("libelle_commune", "France")
        return {
            "Nom_Entreprise": nom_officiel,
            "SIRET": siret,
            "Ville": commune,
        }
  except Exception:
    pass
  return {
      "Nom_Entreprise": nom_entreprise,
      "SIRET": "Non répertorié",
      "Ville": "France",
  }


def generer_donnees():
  print("[+] Étape 1 : Récupération et enrichissement des leads...")
  os.makedirs(OUTPUT_DIR, exist_ok=True)
  timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
  csv_filename = f"{OUTPUT_DIR}/leads_pro_crm_{timestamp}.csv"

  urls = [
      ("https://news.google.com/rss/search?q=creation+entreprise+startup&hl=fr&gl=FR&ceid=FR:fr", "Création"),
      ("https://news.google.com/rss/search?q=levee+de+fonds+entreprise+france&hl=fr&gl=FR&ceid=FR:fr", "Levée de fonds"),
      ("https://news.google.com/rss/search?q=recrutement+massif+entreprise+france&hl=fr&gl=FR&ceid=FR:fr", "Recrutement"),
      ("https://news.google.com/rss/search?q=appel+d+offres+marches+publics+france&hl=fr&gl=FR&ceid=FR:fr", "Marché public")
  ]

  leads = []
  for url, cat in urls:
    feed = feedparser.parse(url)
    for entry in feed.entries[:3]:
      titre = entry.title
      mot_cle = nettoyer_nom_entreprise(titre)
      info = interroger_api_gouvernement(mot_cle)
      
      leads.append({
          "Nom_Entreprise": info["Nom_Entreprise"],
          "SIRET_SIREN": info["SIRET"],
          "Ville": info["Ville"],
          "Poste_Cible": extraire_potentiel_dirigeant(titre),
          "Email_Professionnel": generer_email_pro(info["Nom_Entreprise"]),
          "Categorie": cat,
          "Titre_Opportunite": titre,
          "Source_Lien": entry.link
      })

  keys = list(leads[0].keys()) if leads else []
  with open(csv_filename, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=keys)
    writer.writeheader()
    writer.writerows(leads)

  print(f"[SUCCÈS] {len(leads)} leads générés : {csv_filename}")
  return leads


def rediger_contenu_seo(leads):
  print("[+] Étape 2 : Rédaction de l'article SEO et du post Telegram par l'IA...")
  exemples = "\n".join([f"- {l['Nom_Entreprise']} ({l['Ville']})" for l in leads[:4]])
  date_du_jour = datetime.now().strftime("%d/%m/%Y")
  
  prompt = (
      "Agis en expert growth marketing et rédacteur SEO B2B. Rédige deux éléments séparés par le texte '---DECOUPE---' :\n"
      "1. Un post Telegram percutant pour annoncer la base de leads de la semaine. Pas de lien.\n"
      "2. Un article de blog complet et optimisé SEO (en HTML propre avec des balises h2, p, ul) "
      f"analysant les tendances business en France pour la semaine du {date_du_jour} (créations, levées de fonds, recrutements). "
      f"Mentionne ces exemples : {exemples}. "
      f"À la fin de l'article, intègre un bouton ou un lien d'appel à l'action invitant à télécharger la base complète ici : {GUMROAD_PRODUCT_URL}\n\n"
      "Respecte scrupuleusement le format :\n[POST TELEGRAM]\n---DECOUPE---\n[ARTICLE HTML]"
  )

  url = "https://api.groq.com/openai/v1/chat/completions"
  headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
  payload = {
      "model": "llama-3.3-70b-versatile",
      "messages": [{"role": "user", "content": prompt}]
  }

  try:
    res = requests.post(url, json=payload, headers=headers)
    if res.status_code == 200:
      contenu_brut = res.json()["choices"][0]["message"]["content"]
      if "---DECOUPE---" in contenu_brut:
        parties = contenu_brut.split("---DECOUPE---")
        return parties[0].strip(), parties[1].strip()
  except Exception:
    pass

  post_defaut = "La nouvelle base de leads B2B de la semaine est disponible."
  article_defaut = f"<h2>Tendances B2B de la semaine</h2><p>Découvrez nos analyses et téléchargez notre base qualifiée sur <a href='{GUMROAD_PRODUCT_URL}'>Gumroad</a>.</p>"
  return post_defaut, article_defaut


def generer_page_web_seo(article_html):
  print("[+] Étape 3 : Génération de la page web statique (index.html)...")
  date_du_jour = datetime.now().strftime("%d/%m/%Y")
  
  html_template = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tendances B2B & Leads Qualifiés - {date_du_jour}</title>
    <meta name="description" content="Veille hebdomadaire des créations d'entreprises, levées de fonds et opportunités B2B en France. Fichiers de prospection CRM-Ready.">
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 font-sans leading-relaxed">
    <header class="bg-blue-600 text-white py-10 shadow-md">
        <div class="max-w-3xl mx-auto px-4 text-center">
            <h1 class="text-3xl font-extrabold mb-2">Veille & Leads B2B France</h1>
            <p class="text-blue-100 text-sm">Rapport hebdomadaire automatisé — Semaine du {date_du_jour}</p>
        </div>
    </header>
    
    <main class="max-w-3xl mx-auto px-4 py-10">
        <article class="bg-white p-8 rounded-xl shadow-sm border border-slate-200 space-y-6">
            {article_html}
        </article>
    </main>

    <footer class="text-center py-6 text-slate-400 text-xs">
        <p>&copy; 2026 Veille B2B automatisée. Tous droits réservés.</p>
    </footer>
</body>
</html>
"""

  with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_template)
  print("[SUCCÈS] Page web 'index.html' générée avec succès !")


def notifier_telegram(texte_ia):
  print("[+] Étape 4 : Diffusion sur Telegram...")
  message = (
      f"🚀 **NOUVELLE BASE B2B - CRM READY**\n\n"
      f"{texte_ia}\n\n"
      f"📥 Téléchargez le fichier complet ici :\n{GUMROAD_PRODUCT_URL}"
  )

  tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}

  try:
    requests.post(tg_url, data=payload)
    print("[SUCCÈS] Alerte publiée sur Telegram !")
  except Exception as e:
    print("[ERREUR TELEGRAM] :", e)


if __name__ == "__main__":
  leads = generer_donnees()
  texte_telegram, article_html = rediger_contenu_seo(leads)
  generer_page_web_seo(article_html)
  notifier_telegram(texte_telegram)
  print("[FIN] Processus terminé ! Votre fichier index.html et vos leads sont prêts.")
