import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Pool CDM 2026 - CS Roussillon", page_icon="⚽", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .main-title { color: #0f172a; text-align: center; font-size: 36px; font-weight: 800; margin-bottom: 5px; }
    .sub-title { color: #dc2626; text-align: center; font-size: 20px; font-weight: bold; margin-bottom: 30px; }
    .section-header { color: #dc2626; border-bottom: 2px solid #dc2626; padding-bottom: 5px; margin-top: 30px; }
    .card { background-color: #ffffff; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>🏆 Le Grand Pool - Coupe du Monde 2026</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Édition Spéciale : Club de Soccer Roussillon</div>", unsafe_allow_html=True)

# --- DONNÉES DE BASE ---
groupes = {
    "Gr A": ["Mexique", "Afrique du Sud", "Corée du Sud", "Tchéquie"],
    "Gr B": ["Canada", "Bosnie-Herz.", "Qatar", "Suisse"],
    "Gr C": ["Brésil", "Maroc", "Haïti", "Écosse"],
    "Gr D": ["États-Unis", "Paraguay", "Australie", "Turquie"],
    "Gr E": ["Allemagne", "Curaçao", "Côte d'Ivoire", "Équateur"],
    "Gr F": ["Pays-Bas", "Japon", "Suède", "Tunisie"],
    "Gr G": ["Belgique", "Égypte", "Iran", "Nouv.-Zélande"],
    "Gr H": ["Espagne", "Cap-Vert", "Arabie Saoudite", "Uruguay"],
    "Gr I": ["France", "Sénégal", "Irak", "Norvège"],
    "Gr J": ["Argentine", "Algérie", "Autriche", "Jordanie"],
    "Gr K": ["Portugal", "RD Congo", "Ouzbékistan", "Colombie"],
    "Gr L": ["Angleterre", "Croatie", "Ghana", "Panama"]
}

toutes_equipes = [eq for liste in groupes.values() for eq in liste]

# --- CONNEXION À GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        return gspread.authorize(credentials)
    return None

sheet = None
ws_pronos = None
ws_res = None

try:
    client = init_connection()
    if client:
        sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/18iRYa5Y5pj8RoXViAPiFKHZ-OOEE1u2_Y50GO4oH50o/edit?usp=sharing")
        ws_pronos = sheet.worksheet("Pronostics")
        ws_res = sheet.worksheet("Resultats")
except Exception as e:
    st.error(f"Erreur de configuration Google Sheets : {e}")

# --- MISE EN CACHE DES LECTURES POUR ÉVITER L'ERREUR 429 ---
@st.cache_data(ttl=60)
def fetch_all_data():
    c = init_connection()
    if c:
        try:
            s = c.open_by_url("https://docs.google.com/spreadsheets/d/18iRYa5Y5pj8RoXViAPiFKHZ-OOEE1u2_Y50GO4oH50o/edit?usp=sharing")
            return s.worksheet("Pronostics").get_all_records(), s.worksheet("Resultats").get_all_records()
        except Exception:
            pass
    return [], []

# --- RECONSTRUCTION DES DONNÉES DEPUIS LE CLOUD ---
pools_joueurs = {}
resultats_officiels = {'1ers': {}, '2es': {}, 'repeches': [], 'qualifies_8es': [], 'qualifies_quarts': [], 'qualifies_demies': [], 'finalistes': [], 'champion': None, 'pire_equipe': None, 'meilleur_buteur': None}

raw_p, raw_r = fetch_all_data()

for row in raw_p:
    part = str(row.get("Participant", ""))
    cat = str(row.get("Categorie", ""))
    cle = str(row.get("Cle", ""))
    val = str(row.get("Valeur", ""))
    if not part: continue
    
    if part not in pools_joueurs:
        pools_joueurs[part] = {'1ers': {}, '2es': {}, 'repeches': [], 'qualifies_8es': [], 'qualifies_quarts': [], 'qualifies_demies': [], 'finalistes': [], 'champion': None, 'pire_equipe': None, 'meilleur_buteur': None}
    
    if cat in ['1ers', '2es']:
        pools_joueurs[part][cat][cle] = val
    elif cat in ['repeches', 'qualifies_8es', 'qualifies_quarts', 'qualifies_demies', 'finalistes']:
        if val not in pools_joueurs[part][cat]: pools_joueurs[part][cat].append(val)
    elif cat in ['champion', 'pire_equipe', 'meilleur_buteur']:
        pools_joueurs[part][cat] = val

for row in raw_r:
    cat = str(row.get("Categorie", ""))
    cle = str(row.get("Cle", ""))
    val = str(row.get("Valeur", ""))
    
    if cat in ['1ers', '2es']:
        resultats_officiels[cat][cle] = val
    elif cat in ['repeches', 'qualifies_8es', 'qualifies_quarts', 'qualifies_demies', 'finalistes']:
        if val not in resultats_officiels[cat]: resultats_officiels[cat].append(val)
    elif cat in ['champion', 'pire_equipe', 'meilleur_buteur']:
        resultats_officiels[cat] = val

# --- FONCTION DE CALCUL DES POINTS ---
def calculer_score(pool, officiel):
    score = 0
    if not officiel or not officiel.get('1ers'): return 0

    for grp in groupes.keys():
        if pool['1ers'].get(grp) == officiel['1ers'].get(grp): score += 20
        if pool['2es'].get(grp) == officiel['2es'].get(grp): score += 10
            
    bons_repeches = set(pool.get('repeches', [])) & set(officiel.get('repeches', []))
    score += len(bons_repeches) * 5

    bons_16es = len(set(pool.get('qualifies_8es', [])) & set(officiel.get('qualifies_8es', [])))
    if officiel.get('qualifies_8es'):
        score += 70 if bons_16es >= 15 else 60 if bons_16es >= 13 else 45 if bons_16es >= 10 else 30 if bons_16es >= 7 else 15

    bons_8es = len(set(pool.get('qualifies_quarts', [])) & set(officiel.get('qualifies_quarts', [])))
    if officiel.get('qualifies_quarts'):
        score += 60 if bons_8es == 8 else 55 if bons_8es == 7 else 50 if bons_8es == 6 else 45 if bons_8es == 5 else bons_8es * 10

    bons_quarts = len(set(pool.get('qualifies_demies', [])) & set(officiel.get('qualifies_demies', [])))
    if officiel.get('qualifies_demies'):
        score += 60 if bons_quarts == 4 else 50 if bons_quarts == 3 else 40 if bons_quarts == 2 else 30 if bons_quarts == 1 else 0

    bons_finalistes = len(set(pool.get('finalistes', [])) & set(officiel.get('finalistes', [])))
    if officiel.get('finalistes'):
        score += 50 if bons_finalistes == 2 else 25 if bons_finalistes == 1 else 0
        
    if officiel.get('champion') and pool.get('champion') == officiel.get('champion'): score += 50
    if officiel.get('pire_equipe') and pool.get('pire_equipe') == officiel.get('pire_equipe'): score += 20
    
    if officiel.get('meilleur_buteur') and pool.get('meilleur_buteur'):
        if str(pool['meilleur_buteur']).strip().lower() == str(officiel['meilleur_buteur']).strip().lower():
            score += 20

    return score

# --- INTERFACE (QUATRE ONGLETS) ---
tab_saisie, tab_admin, tab_classement, tab_sommaire = st.tabs([
    "📝 Soumettre mon Pool", 
    "⚙️ Administration", 
    "📊 Classement Général", 
    "🔍 Sommaire des Choix"
])

def afficher_formulaire(is_admin=False):
    prefix = "admin_" if is_admin else "user_"
    
    if not is_admin:
        if not sheet:
            st.warning("⚠️ L'application n'est pas connectée à Google Sheets.")
        joueur_actuel = st.text_input("Votre Prénom et Nom (ex: Pierre Tremblay) :", key="nom_joueur")
    else:
        joueur_actuel = "Officiel"
        st.warning("⚠️ Section Administration réservée à la saisie des résultats réels de la FIFA.")

    st.markdown("<h3 class='section-header'>1. Phase de Groupes</h3>", unsafe_allow_html=True)
    choix_1ers, choix_2es, choix_3es = {}, {}, {}
    
    col1, col2, col3, col4 = st.columns(4)
    cols = [col1, col2, col3, col4] * 3
    
    for i, (grp, equipes) in enumerate(groupes.items()):
        with cols[i]:
            st.markdown(f"**{grp}**")
            p1 = st.selectbox("1er", ["-"] + equipes, key=f"{prefix}1er_{grp}")
            p2 = st.selectbox("2e", ["-"] + [e for e in equipes if e != p1], key=f"{prefix}2e_{grp}")
            p3 = st.selectbox("3e", ["-"] + [e for e in equipes if e not in [p1, p2]], key=f"{prefix}3e_{grp}")
            
            if p1 != "-": choix_1ers[grp] = p1
            if p2 != "-": choix_2es[grp] = p2
            if p3 != "-": choix_3es[grp] = p3

    st.markdown("<h3 class='section-header'>2. Repêchages (Les Meilleurs 3es)</h3>", unsafe_allow_html=True)
    liste_3es = list(choix_3es.values())
    repeches = st.multiselect("Sélectionnez les 8 équipes repêchées :", liste_3es, max_selections=8, key=f"{prefix}repeches")

    qualifies_32 = list(choix_1ers.values()) + list(choix_2es.values()) + repeches
    
    st.markdown("<h3 class='section-header'>3. L'Arbre Éliminatoire</h3>", unsafe_allow_html=True)
    if len(qualifies_32) < 32 and not is_admin:
        st.warning("Veuillez sélectionner vos 32 qualifiés pour débloquer la suite de l'arbre.")
        return

    qualifies_16 = st.multiselect("Les 16 équipes qui passeront en 8es :", qualifies_32, max_selections=16, key=f"{prefix}q16")
    qualifies_8 = st.multiselect("Les 8 équipes qui passeront en Quarts :", qualifies_16 if qualifies_16 else qualifies_32, max_selections=8, key=f"{prefix}q8")
    qualifies_4 = st.multiselect("Les 4 Demi-finalistes :", qualifies_8 if qualifies_8 else qualifies_32, max_selections=4, key=f"{prefix}q4")
    finalistes = st.multiselect("Les 2 Finalistes :", qualifies_4 if qualifies_4 else qualifies_32, max_selections=2, key=f"{prefix}fin")
    champion = st.selectbox("Le CHAMPION 🏆 :", ["-"] + finalistes, key=f"{prefix}champ")
    
    st.markdown("<h3 class='section-header'>4. Bonus / Malus</h3>", unsafe_allow_html=True)
    col_bonus1, col_bonus2 = st.columns(2)
    with col_bonus1:
        pire_equipe = st.selectbox("La Pire équipe du tournoi (+20 pts) :", ["-"] + toutes_equipes, key=f"{prefix}pire")
    with col_bonus2:
        meilleur_buteur = st.text_input("Meilleur Buteur / Golden Boot (+20 pts) :", placeholder="ex: Kylian Mbappé", key=f"{prefix}buteur")

    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("💾 ENREGISTRER " + ("LES DONNÉES OFFICIELLES" if is_admin else "MON BRACKET"), type="primary", key=f"{prefix}btn_save"):
        if not is_admin and not joueur_actuel:
            st.error("Erreur : Veuillez renseigner votre nom avant de valider.")
            return
        
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        rows_to_append = []
        
        for grp, val in choix_1ers.items():
            rows_to_append.append([ts, joueur_actuel, '1ers', grp, val] if not is_admin else [cat for cat in ['1ers', grp, val]])
        for grp, val in choix_2es.items():
            rows_to_append.append([ts, joueur_actuel, '2es', grp, val] if not is_admin else [cat for cat in ['2es', grp, val]])
        for val in repeches:
            rows_to_append.append([ts, joueur_actuel, 'repeches', 'eq', val] if not is_admin else [cat for cat in ['repeches', 'eq', val]])
        for val in qualifies_16:
            rows_to_append.append([ts, joueur_actuel, 'qualifies_8es', 'eq', val] if not is_admin else [cat for cat in ['qualifies_8es', 'eq', val]])
        for val in qualifies_8:
            rows_to_append.append([ts, joueur_actuel, 'qualifies_quarts', 'eq', val] if not is_admin else [cat for cat in ['qualifies_quarts', 'eq', val]])
        for val in qualifies_4:
            rows_to_append.append([ts, joueur_actuel, 'qualifies_demies', 'eq', val] if not is_admin else [cat for cat in ['qualifies_demies', 'eq', val]])
        for val in finalistes:
            rows_to_append.append([ts, joueur_actuel, 'finalistes', 'eq', val] if not is_admin else [cat for cat in ['finalistes', 'eq', val]])
            
        if champion != "-":
            rows_to_append.append([ts, joueur_actuel, 'champion', 'global', champion] if not is_admin else [cat for cat in ['champion', 'global', champion]])
        if pire_equipe != "-":
            rows_to_append.append([ts, joueur_actuel, 'pire_equipe', 'global', pire_equipe] if not is_admin else [cat for cat in ['pire_equipe', 'global', pire_equipe]])
        if meilleur_buteur and meilleur_buteur.strip() != "":
            rows_to_append.append([ts, joueur_actuel, 'meilleur_buteur', 'global', meilleur_buteur.strip()] if not is_admin else [cat for cat in ['meilleur_buteur', 'global', meilleur_buteur.strip()]])
            
        c = init_connection()
        if c:
            try:
                s = c.open_by_url("https://docs.google.com/spreadsheets/d/18iRYa5Y5pj8RoXViAPiFKHZ-OOEE1u2_Y50GO4oH50o/edit?usp=sharing")
                target_ws = s.worksheet("Resultats") if is_admin else s.worksheet("Pronostics")
                if is_admin:
                    target_ws.clear()
                    target_ws.append_row(['Categorie', 'Cle', 'Valeur'])
                    target_ws.append_rows(rows_to_append)
                else:
                    target_ws.append_rows(rows_to_append)
                
                fetch_all_data.clear()
                st.success("Données synchronisées avec succès sur Google Sheets ! Veuillez rafraîchir la page.")
            except Exception as e:
                st.error(f"Erreur d'écriture Sheets : {e}")

with tab_saisie:
    afficher_formulaire(is_admin=False)

with tab_admin:
    afficher_formulaire(is_admin=True)

with tab_classement:
    st.markdown("<h3 class='section-header'>📊 Classement en Direct du Club</h3>", unsafe_allow_html=True)
    if not resultats_officiels or not resultats_officiels.get('1ers'):
        st.info("Le tournoi n'a pas encore débuté ou aucun résultat officiel n'a été saisi.")
        
    scores = []
    for nom_joueur, data_pool in pools_joueurs.items():
        pts = calculer_score(data_pool, resultats_officiels)
        scores.append({"Rang": 1, "Nom du Participant": nom_joueur, "Points": pts})
            
    if scores:
        df_scores = pd.DataFrame(scores).sort_values(by="Points", ascending=False).reset_index(drop=True)
        df_scores["Rang"] = df_scores.index + 1
        st.dataframe(df_scores.set_index("Rang"), use_container_width=True)
    else:
        st.write("En attente des premières soumissions des membres du club.")

# --- NOUVEL ONGLET : SOMMAIRE DES CHOIX DES COLLÈGUES ---
with tab_sommaire:
    st.markdown("<h3 class='section-header'>🔍 Visualiser l'arbre complet d'un participant</h3>", unsafe_allow_html=True)
    
    if not pools_joueurs:
        st.info("Aucun prono n'a encore été enregistré par les membres du club.")
    else:
        # Menu déroulant contenant la liste de tous ceux qui ont soumis un prono
        collaborateur = st.selectbox("Choisissez un collègue pour voir ses prédictions :", sorted(list(pools_joueurs.keys())))
        
        if collaborateur:
            p_data = pools_joueurs[collaborateur]
            
            # 1. Résumé des Groupes
            st.subheader("1. Classement des Poules")
            gr_rows = []
            for grp in groupes.keys():
                gr_rows.append({
                    "Groupe": grp,
                    "Vainqueur (1er)": p_data['1ers'].get(grp, "-"),
                    "Deuxième (2e)": p_data['2es'].get(grp, "-")
                })
            st.table(pd.DataFrame(gr_rows).set_index("Groupe"))
            
            st.write(f"**Les 8 troisièmes repêchés pour les 16es :** {', '.join(p_data.get('repeches', [])) if p_data.get('repeches') else 'Aucun'}")
            
            # 2. Arbre éliminatoire en cascade
            st.subheader("2. Tableau Éliminatoire Prédit")
            col_tree1, col_tree2 = st.columns(2)
            with col_tree1:
                st.write("**Équipes en 8es de finale :**")
                st.caption(", ".join(p_data.get('qualifies_8es', [])) if p_data.get('qualifies_8es') else "-")
                
                st.write("**Équipes en Quarts de finale :**")
                st.caption(", ".join(p_data.get('qualifies_quarts', [])) if p_data.get('qualifies_quarts') else "-")
                
            with col_tree2:
                st.write("**Équipes en Demi-finales :**")
                st.caption(", ".join(p_data.get('qualifies_demies', [])) if p_data.get('qualifies_demies') else "-")
                
                st.write("**Les deux Finalistes :**")
                st.caption(", ".join(p_data.get('finalistes', [])) if p_data.get('finalistes') else "-")
            
            st.markdown(f"### 🏆 Champion du Monde pronostiqué : **{p_data.get('champion', '-')}**")
            
            # 3. Bonus / Malus
            st.subheader("3. Choix Annexes")
            st.write(f"❌ **Pire équipe de la compétition :** {p_data.get('pire_equipe', '-')}")
            st.write(f"👟 **Soulier d'Or (Golden Boot) :** {p_data.get('meilleur_buteur', '-')}")
