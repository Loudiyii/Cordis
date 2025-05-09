import streamlit as st
import pandas as pd
import plotly.express as px

# ⚙️ Configuration de la page
st.set_page_config(layout="wide", page_title="Dashboard CORDIS")
st.title("📊 Tableau de bord des projets financés par CORDIS")
st.caption("⚠️ Chargement en cours, merci de patienter 🙏")

# 📂 Choix du fichier source
dataset_choice = st.sidebar.radio("📁 Sélection du dataset :", [
    "CORDIS - Organismes financé par EU/FR",
    "CORDIS - Base Total"
])

# 🔄 Chargement dynamique en fonction du choix
@st.cache_data
def load_data(path):
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip().str.lower()
    return df

with st.spinner("Chargement des données..."):
    if dataset_choice == "CORDIS - Organismes financé par EU/FR":
        filepath = r"Cordis_projets_communs_key.xlsx"
    else:
        filepath = r"cleanbasefinal_with_keywords.xlsx"

    df = load_data(filepath)

st.success(f"✅ Dataset chargé : {dataset_choice}")

# ✅ Vérification colonnes nécessaires
required_cols = ['id', 'startdate', 'enddate', 'totalcost_project', 'ecmaxcontribution', 'eccontribution']
missing = [col for col in required_cols if col not in df.columns]
if missing:
    st.error(f"❌ Colonnes manquantes : {missing}")
    st.stop()

# 🔁 Prétraitement
df['startdate'] = pd.to_datetime(df['startdate'], errors='coerce')
df['enddate'] = pd.to_datetime(df['enddate'], errors='coerce')

for col in ['totalcost_project', 'ecmaxcontribution', 'eccontribution', 'neteccontribution']:
    if col in df.columns:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
            errors='coerce'
        )

df['startyear'] = df['startdate'].dt.year

# 🔏 Filtres
st.sidebar.header("🎯 Filtres")
filters = {
    'status': st.sidebar.multiselect("Statut", sorted(df['status'].dropna().unique())) if 'status' in df.columns else [],
    'year': st.sidebar.multiselect("Année de début", sorted(df['startyear'].dropna().astype(int).unique())),
    'role': st.sidebar.multiselect("Rôle", sorted(df['role'].dropna().unique())) if 'role' in df.columns else [],
    'legalbasis': st.sidebar.multiselect("Cadre légal", sorted(df['legalbasis'].dropna().unique())) if 'legalbasis' in df.columns else [],
    'name': st.sidebar.multiselect("Organisation", sorted(df['name'].dropna().unique())) if 'name' in df.columns else [],
    'city': st.sidebar.multiselect("Ville", sorted(df['city'].dropna().unique())) if 'city' in df.columns else []
}

for key, values in filters.items():
    if values:
        col = 'startyear' if key == 'year' else key
        df = df[df[col].isin(values)]

# 📊 Agrégation des projets
df_proj = df.groupby('id', as_index=False).agg(
    id=('id', 'first'),
    title=('title', 'first'),
    totalcost=('totalcost_project', 'first'),
    ecmaxcontribution=('ecmaxcontribution', 'first'),
    eccontribution=('eccontribution', 'sum'),
    startdate=('startdate', 'min'),
    enddate=('enddate', 'max')
)
df_proj['duration_days'] = (df_proj['enddate'] - df_proj['startdate']).dt.days
df_proj['startyear'] = df_proj['startdate'].dt.year

# 🔢 KPIs
org_col = 'name' if 'name' in df.columns else 'organizationurl'
num_projects = df_proj['id'].nunique()
num_orgs = df[org_col].nunique() if org_col in df.columns else 0
sum_totalcost = df_proj['totalcost'].sum()
sum_ecfunding = df_proj['ecmaxcontribution'].sum()
avg_ecfunding = df_proj['ecmaxcontribution'].mean()
avg_totalcost = df_proj['totalcost'].mean()
med_ecfunding = df_proj['ecmaxcontribution'].median()
med_totalcost = df_proj['totalcost'].median()

proj_max = df_proj.loc[df_proj['totalcost'].idxmax()] if df_proj['totalcost'].notna().any() else None
proj_longest = df_proj.loc[df_proj['duration_days'].idxmax()]

most_common_id = df['id'].value_counts().idxmax()
nb_occurrences = df['id'].value_counts().max()
proj_title_most_common = df[df['id'] == most_common_id]['title'].iloc[0] if 'title' in df.columns else "(titre non dispo)"

# 📊 Affichage KPIs
st.subheader("🔢 Indicateurs clés")
c1, c2, c3 = st.columns(3)
c1.metric("# Projets", num_projects)
c2.metric("Financement EC (€)", f"{sum_ecfunding:,.0f}")
c3.metric("Total Cost (€)", f"{sum_totalcost:,.0f}")

st.markdown(f"👥 Projet avec le plus de lignes (partenaires) : **{proj_title_most_common}** (ID {most_common_id}) — {nb_occurrences} lignes")
st.markdown(f"- Moy. EC fund : **{avg_ecfunding:,.0f} €**, Médiane : **{med_ecfunding:,.0f} €**")
st.markdown(f"- Moy. totalCost : **{avg_totalcost:,.0f} €**, Médiane : **{med_totalcost:,.0f} €**")
if proj_max is not None:
    st.markdown(f"💰 Projet le + cher : **{proj_max['title']}** (ID {proj_max['id']}) — {proj_max['totalcost']:,.0f} €")
st.markdown(f"⏳ Projet le + long : **{proj_longest['title']}** (ID {proj_longest['id']}) — {proj_longest['duration_days']} jours")

# 📈 Financement UE par année
st.subheader("📈 Financement UE par année")
df_year = df_proj.groupby('startyear', as_index=False).agg(year_ec=('ecmaxcontribution', 'sum'))
fig1 = px.bar(
    df_year,
    x='startyear',
    y='year_ec',
    title="Financement UE par année en €",
    color='year_ec',
    text=df_year['year_ec'].map('{:,.0f}'.format)
)
fig1.update_traces(textposition="outside")
fig1.update_layout(
    yaxis_tickformat=',',
    coloraxis_colorbar=dict(title="€", tickformat=',')
)

st.plotly_chart(fig1, use_container_width=True)

# 📝 Extraction des coordonnées si 'geolocation'
if 'geolocation' in df.columns:
    df[['lat', 'long']] = df['geolocation'].str.split(',', expand=True)
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['long'] = pd.to_numeric(df['long'], errors='coerce')

# 🏢 Top organisations avec ville
if org_col in df.columns and 'city' in df.columns:
    st.subheader("🏢 Top 10 organisations par contribution UE")
    df_org = df.groupby([org_col, 'city'], as_index=False).agg(ec_total=('ecmaxcontribution', 'sum'))
    df_org = df_org.sort_values(by='ec_total', ascending=False).head(10)
    fig2 = px.bar(
    df_org,
    x=df_org['ec_total'],
    y=org_col,
    orientation='h',
    title="Top Organisations UE (en milliards €)",
    color=df_org['ec_total'],
    hover_data=['city'],
    text=(df_org['ec_total'] / 1_000_000_000).map('{:,.2f} B'.format)
)
fig2.update_traces(textposition='outside')
fig2.update_layout(xaxis_tickformat=',.2f', coloraxis_colorbar=dict(title='Mds €', tickformat=',.2f'))
st.plotly_chart(fig2, use_container_width=True)


# 📊 Statuts
if 'status' in df.columns:
    st.subheader("📊 Répartition des statuts")
    status_counts = df.drop_duplicates('id')['status'].value_counts().reset_index()
    status_counts.columns = ['status', 'count']
    fig3 = px.pie(status_counts, names='status', values='count', title="Statut des projets")
    st.plotly_chart(fig3, use_container_width=True)

# 📊 Rôles
if 'role' in df.columns:
    st.subheader("📊 Répartition des rôles")
    role_counts = df.drop_duplicates(['id', 'role'])['role'].value_counts().reset_index()
    role_counts.columns = ['role', 'count']
    fig4 = px.pie(role_counts, names='role', values='count', title="Rôle des organisations")
    st.plotly_chart(fig4, use_container_width=True)

# 🌍 Carte des projets
if 'lat' in df.columns and 'long' in df.columns:
    st.subheader("📍 Carte des lieux avec le plus de projets")
    df_map = df.groupby(['lat', 'long', 'city'], as_index=False).agg(nb_projets=('id', 'nunique')).dropna()
    fig_map = px.scatter_mapbox(df_map, lat='lat', lon='long', size='nb_projets', color='nb_projets', color_continuous_scale='Viridis', zoom=4, height=600, title="Nombre de projets par localisation", hover_name='city')
    fig_map.update_layout(mapbox_style="open-street-map")
    st.plotly_chart(fig_map, use_container_width=True)

# 🏆 Top 10 localisations
df['city_clean'] = df['city'].str.lower().str.strip()
df['city_clean'] = df['city_clean'].str.replace(r"paris\s*\d*", "paris", regex=True)
df['city_clean'] = df['city_clean'].str.title()

st.subheader("🏆 Top 10 des villes avec le plus de projets (regroupées)")
top_locations = (
    df.groupby('city_clean', as_index=False)
      .agg(nb_projets=('id', 'nunique'))
      .sort_values(by='nb_projets', ascending=False)
      .head(10)
)
st.dataframe(top_locations)


# 📋 Table finale
st.subheader("📋 Données projets filtrées (complètes)")
st.dataframe(df)

# 📅 Export CSV
st.download_button(
    label="📥 Télécharger les données projets filtrées",
    data=df.to_csv(index=False).encode('utf-8'),
    file_name=f"projets_cordis_filtrés_{'siren' if 'siren' in filepath.lower() else 'complet'}.csv",
    mime='text/csv'
)
