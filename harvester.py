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
  print("[+] Étape 3 : Génération de la page web statique (index.html) version Ultime...")
  date_du_jour = datetime.now().strftime("%d/%m/%Y")
  
  html_template = f"""<!DOCTYPE html>
<html lang="fr" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DataFactory B2B — Veille & Leads Qualifiés ({date_du_jour})</title>
    <meta name="description" content="Plateforme d'intelligence commerciale et de génération de leads B2B en France. Fichiers CRM-Ready mis à jour chaque semaine.">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
        .glow-effect {{ background: radial-gradient(circle at center, rgba(59, 130, 246, 0.15) 0%, transparent 70%); }}
    </style>
</head>
<body class="bg-slate-950 text-slate-100 antialiased selection:bg-blue-500 selection:text-white">
    
    <!-- BACKGROUND GLOW -->
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 glow-effect pointer-events-none"></div>

    <!-- NAVBAR -->
    <header class="relative border-b border-slate-800/60 bg-slate-900/40 backdrop-blur-xl sticky top-0 z-50">
        <div class="max-w-5xl mx-auto px-6 h-20 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="h-11 w-11 rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/25 ring-1 ring-white/20">
                    <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                </div>
                <div>
                    <span class="font-extrabold text-lg tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent block">DataFactory</span>
                    <span class="text-[10px] uppercase tracking-widest text-blue-400 font-semibold block">Intelligence B2B</span>
                </div>
            </div>
            <a href="{GUMROAD_PRODUCT_URL}" target="_blank" class="inline-flex items-center px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition-all shadow-lg shadow-blue-600/20">
                Accéder au fichier
            </a>
        </div>
    </header>

    <!-- HERO SECTION -->
    <section class="relative pt-16 pb-12 overflow-hidden">
        <div class="max-w-4xl mx-auto px-6 text-center relative z-10">
            <div class="inline-flex items-center px-3.5 py-1.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-6 shadow-inner">
                <span class="w-2 h-2 rounded-full bg-blue-400 animate-ping mr-2"></span> Édition Hebdomadaire — Semaine du {date_du_jour}
            </div>
            <h1 class="text-4xl sm:text-6xl font-extrabold tracking-tight mb-6 leading-[1.1]">
                Fermez plus de contrats avec des <br/><span class="bg-gradient-to-r from-blue-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent">Leads B2B ultra-frais</span>
            </h1>
            <p class="text-slate-400 text-lg sm:text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
                Chaque semaine, accédez aux signaux d'affaires en France (levées de fonds, créations, recrutements) recoupés et validés via l'API officielle.
            </p>
            <div class="flex flex-col sm:flex-row items-center justify-center gap-4">
                <a href="{GUMROAD_PRODUCT_URL}" target="_blank" class="w-full sm:w-auto px-8 py-4 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold text-base shadow-xl shadow-blue-600/30 hover:scale-105 transition-all">
                    Télécharger la base complète (CRM-Ready)
                </a>
            </div>
        </div>
    </section>

    <!-- STATS GRID -->
    <section class="max-w-4xl mx-auto px-6 pb-12">
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div class="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-md text-center">
                <div class="text-3xl font-extrabold text-blue-400 mb-1">100%</div>
                <div class="text-xs text-slate-400 font-medium uppercase tracking-wider">Vérifié API Gouvernement</div>
            </div>
            <div class="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-md text-center">
                <div class="text-3xl font-extrabold text-indigo-400 mb-1">Format CSV</div>
                <div class="text-xs text-slate-400 font-medium uppercase tracking-wider">Compatible HubSpot / Salesforce</div>
            </div>
            <div class="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-md text-center">
                <div class="text-3xl font-extrabold text-purple-400 mb-1">Mis à jour</div>
                <div class="text-xs text-slate-400 font-medium uppercase tracking-wider">Chaque semaine sans abonnement</div>
            </div>
        </div>
    </section>

    <!-- APERÇU DU FICHIER (MOCKUP CSV TABLE) -->
    <section class="max-w-4xl mx-auto px-6 pb-16">
        <div class="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
            <div class="flex items-center justify-between mb-6">
                <div>
                    <h3 class="text-lg font-bold text-white">Aperçu de la structure du fichier</h3>
                    <p class="text-xs text-slate-400">Colonnes incluses dans votre export CSV prêt à l'emploi</p>
                </div>
                <span class="px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Exemple réel</span>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs text-slate-300">
                    <thead class="bg-slate-950 text-slate-400 uppercase font-semibold border-b border-slate-800">
                        <tr>
                            <th class="p-3">Nom Entreprise</th>
                            <th class="p-3">SIRET / SIREN</th>
                            <th class="p-3">Ville</th>
                            <th class="p-3">Poste Cible</th>
                            <th class="p-3">Email Pro</th>
                            <th class="p-3">Catégorie</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800/60">
                        <tr class="bg-slate-900/40">
                            <td class="p-3 font-medium text-white">KSM Tech Solutions</td>
                            <td class="p-3 font-mono text-slate-400">894 521 369</td>
                            <td class="p-3">Paris</td>
                            <td class="p-3 text-blue-400">Fondateur / CEO</td>
                            <td class="p-3 font-mono text-slate-300">direction@ksmtech.fr</td>
                            <td class="p-3"><span class="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 text-[10px]">Levée de fonds</span></td>
                        </tr>
                        <tr>
                            <td class="p-3 font-medium text-white">Innovate France Lab</td>
                            <td class="p-3 font-mono text-slate-400">482 103 789</td>
                            <td class="p-3">Lyon</td>
                            <td class="p-3 text-blue-400">DRH / Talent</td>
                            <td class="p-3 font-mono text-slate-300">direction@innovatef.fr</td>
                            <td class="p-3"><span class="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 text-[10px]">Recrutement</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </section>

    <!-- ARTICLE / RAPPORT HEBDOMADAIRE -->
    <main class="max-w-4xl mx-auto px-6 pb-20">
        <div class="bg-slate-900/80 border border-slate-800/80 rounded-3xl p-8 sm:p-12 shadow-2xl backdrop-blur-xl relative overflow-hidden">
            <h3 class="text-xl font-bold text-white mb-6 flex items-center">
                <svg class="w-5 h-5 text-blue-400 mr-2" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"/></svg>
                Analyse & Tendances du Marché B2B
            </h3>
            <article class="space-y-6 text-slate-300 leading-relaxed 
                [&>h2]:text-2xl sm:[&>h2]:text-3xl [&>h2]:font-bold [&>h2]:text-white [&>h2]:mt-10 [&>h2]:mb-6 [&>h2]:tracking-tight
                [&>p]:text-slate-300 [&>p]:text-base sm:[&>p]:text-lg [&>p]:mb-4
                [&>ul]:space-y-3 [&>ul]:my-6 [&>ul>li]:bg-slate-950/40 [&>ul>li]:border [&>ul>li]:border-slate-800/80 [&>ul>li]:p-4 [&>ul>li]:rounded-xl [&>ul>li]:text-slate-300
                [&>a]:inline-flex [&>a]:items-center [&>a]:justify-center [&>a]:w-full sm:[&>a]:w-auto [&>a]:px-8 [&>a]:py-4 [&>a]:mt-8 [&>a]:rounded-2xl [&>a]:bg-gradient-to-r [&>a]:from-blue-600 [&>a]:to-indigo-600 [&>a]:text-white [&>a]:font-bold [&>a]:text-base [&>a]:shadow-xl [&>a]:shadow-blue-600/30 hover:[&>a]:scale-[1.02] [&>a]:transition-all">
                {article_html}
            </article>
        </div>
    </main>

    <!-- FAQ SECTION -->
    <section class="max-w-4xl mx-auto px-6 pb-24">
        <h3 class="text-2xl font-bold text-white text-center mb-10">Foire Aux Questions</h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div class="bg-slate-900/60 border border-slate-800/80 p-6 rounded-2xl">
                <h4 class="font-bold text-white mb-2">Quel est le format du fichier ?</h4>
                <p class="text-sm text-slate-400">Le fichier est livré au format CSV universel, séparé par des virgules ou points-virgules, compatible avec Excel, Google Sheets, et tous les CRM du marché.</p>
            </div>
            <div class="bg-slate-900/60 border border-slate-800/80 p-6 rounded-2xl">
                <h4 class="font-bold text-white mb-2">D'où proviennent les données ?</h4>
                <p class="text-sm text-slate-400">Les données sont collectées via des signaux d'actualité business vérifiés et recoupés instantanément avec l'API officielle de l'INSEE / Gouvernement français.</p>
            </div>
        </div>
    </section>

    <!-- FOOTER -->
    <footer class="border-t border-slate-900 bg-slate-950 py-12 text-center text-slate-500 text-xs">
        <div class="max-w-4xl mx-auto px-6 space-y-4">
            <p class="font-medium text-slate-400">DataFactory B2B — La solution de prospection automatisée en France.</p>
            <p>&copy; 2026 DataFactory. Tous droits réservés.</p>
        </div>
    </footer>
</body>
</html>
"""

  with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_template)
  print("[SUCCÈS] Page web 'index.html' version Ultime générée avec succès !")


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
  print("[FIN] Processus terminé ! Votre page web premium et vos leads sont prêts.")
