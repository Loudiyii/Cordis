import streamlit as st
import pandas as pd
import plotly.express as px

# ⚙️ Configuration de la page
st.set_page_config(layout="wide", page_title="Dashboard CORDIS")
st.title("📊 Tableau de bord des projets financés par CORDIS")
st.caption("⚠️ Chargement en cours, merci de patienter 🙏")

# 📂 Choix du fichier source
dataset_choice = st.sidebar.radio("📁 Sélection du dataset :", [
    "CORDIS - Organismes financés par EU/FR",
    "CORDIS - Base Total"
])

# 🔄 Chargement dynamique en fonction du choix
@st.cache_data
def load_data(path):
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip().str.lower()
    return df

with st.spinner("Chargement des données..."):
    if dataset_choice == "CORDIS - Organismes financés par EU/FR":
        filepath = r"Cordis_projets_communs_key.xlsx"
    else:
        filepath = r"cleanbasefinal_with_keywords.xlsx"

    df = load_data(filepath)

st.success(f"✅ Dataset chargé : {dataset_choice}")

# ✅ Vérification colonnes nécessaires
# Prétraitement
df['startdate'] = pd.to_datetime(df['startdate'], errors='coerce')
df['enddate'] = pd.to_datetime(df['enddate'], errors='coerce')
df['startyear'] = df['startdate'].dt.year

for col in ['totalcost_project', 'ecmaxcontribution', 'eccontribution', 'neteccontribution']:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors='coerce')

# Filtres dynamiques
st.sidebar.header("🎯 Filtres")
filters = {
    'status': st.sidebar.multiselect("Statut", sorted(df['status'].dropna().unique())) if 'status' in df.columns else [],
    'year': st.sidebar.multiselect("Année", sorted(df['startyear'].dropna().unique())),
    'role': st.sidebar.multiselect("Rôle", sorted(df['role'].dropna().unique())) if 'role' in df.columns else [],
    'legalbasis': st.sidebar.multiselect("Cadre légal", sorted(df['legalbasis'].dropna().unique())) if 'legalbasis' in df.columns else [],
    'name': st.sidebar.multiselect("Organisation", sorted(df['name'].dropna().unique())) if 'name' in df.columns else [],
    'city': st.sidebar.multiselect("Ville", sorted(df['city'].dropna().unique())) if 'city' in df.columns else [],
    'acronym': st.sidebar.multiselect("Acronyme", sorted(df['acronym'].dropna().unique())) if 'acronym' in df.columns else []
}

df_filtered = df.copy()
for key, values in filters.items():
    if values:
        col = 'startyear' if key == 'year' else key
        df_filtered = df_filtered[df_filtered[col].isin(values)]

# Agrégation principale
df_proj = df_filtered.groupby('id', as_index=False).agg(
    title=('title', 'first'),
    totalcost=('totalcost_project', 'first'),
    ecmaxcontribution=('ecmaxcontribution', 'first'),
    startdate=('startdate', 'min'),
    enddate=('enddate', 'max')
)
df_proj['duration_days'] = (df_proj['enddate'] - df_proj['startdate']).dt.days
df_proj['startyear'] = df_proj['startdate'].dt.year

# Page Tableau de bord global
if 1==1:
    st.title("📊 Tableau de bord CORDIS 2014-2023")

    # KPIs
    st.subheader("🔢 Indicateurs clés")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nombre projets", df_proj['title'].nunique())
    col2.metric("Financement UE (€)", f"{df_proj['ecmaxcontribution'].sum():,.0f}")
    col3.metric("Coût total (€)", f"{df_proj['totalcost'].sum():,.0f}")
    if 'keywords' in df.columns:
        pct_na = df_filtered['keywords'].isna().mean() * 100
        col4.metric("% sans mots-clés", f"{pct_na:.1f}%")

    # Tabs avec visualisations
    tab1, tab2, tab3, tab4, tab5 ,tab6= st.tabs([
        "📈 Financement par année",
        "🏢 Top organisations",
        "📊 Statuts",
        "📊 Rôles",
        "🌍 Carte des projets",
        "Données brutes"
    ])

    with tab1:
        df_year = df_proj.groupby('startyear').agg(total_funding=('ecmaxcontribution', 'sum')).reset_index()
        fig = px.bar(df_year, x='startyear', y='total_funding', text='total_funding', color='total_funding')
        fig.update_traces(textposition='outside')
        fig.update_layout(yaxis_tickformat=',')
        st.plotly_chart(fig, use_container_width=True)

        # 🔍 Insight automatique
        peak_year = df_year.loc[df_year['total_funding'].idxmax()]
        st.markdown(
            f"🔍 **Insight :** L'année avec le plus de financement est **{int(peak_year['startyear'])}**, "
            f"avec **{peak_year['total_funding']:,.0f} €** alloués."
        )
        st.title("📅 Top 10 projets les plus financés par année")
        available_years = sorted(df_filtered['startyear'].dropna().unique())
        selected_year = st.selectbox("🗓️ Choisir une année", available_years)
        df_year = df_filtered[df_filtered['startyear'] == selected_year]
        df_top10 = df_year.groupby(['id', 'title'], as_index=False).agg(financement=('ecmaxcontribution', 'sum')).sort_values(by='financement', ascending=False).head(10)
        st.dataframe(df_top10)

    with tab2:
        if 'name' in df_filtered.columns and 'city' in df_filtered.columns:
            df_org = df_filtered.groupby(['name', 'city']).agg(ec_total=('ecmaxcontribution', 'sum')).reset_index()
            df_top = df_org.sort_values(by='ec_total', ascending=False).head(10)
            fig2 = px.bar(df_top, x='ec_total', y='name', orientation='h', text='ec_total', color='ec_total', hover_data=['city'])
            fig2.update_traces(textposition='outside')
            fig2.update_layout(xaxis_tickformat=',')
            st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        if 'status' in df_filtered.columns:
            status_counts = df_filtered.drop_duplicates('id')['status'].value_counts().reset_index()
            status_counts.columns = ['status', 'count']
            fig3 = px.pie(status_counts, names='status', values='count', title="Statut des projets")
            st.plotly_chart(fig3, use_container_width=True)

        # 🧠 Insight automatique
        dominant_status = status_counts.iloc[0]['status']
        dominant_pct = round(status_counts.iloc[0]['count'] / status_counts['count'].sum() * 100, 1)
        st.markdown(f"🔍 **Insight :** La majorité des projets sont **{dominant_status.lower()}** ({dominant_pct}%).")

    with tab4:
        if 'role' in df_filtered.columns:
            role_counts = df_filtered.drop_duplicates(['id', 'role'])['role'].value_counts().reset_index()
            role_counts.columns = ['role', 'count']
            fig4 = px.pie(role_counts, names='role', values='count', title="Rôle des entités")
            st.plotly_chart(fig4, use_container_width=True)

            # 🧠 Insight automatique
            dominant_role = role_counts.iloc[0]['role']
            dominant_pct = round(role_counts.iloc[0]['count'] / role_counts['count'].sum() * 100, 1)
            st.markdown(f"🔍 **Insight :** Le rôle le plus fréquent est **{dominant_role.lower()}** ({dominant_pct}%).")


    with tab5:
        if 'geolocation' in df_filtered.columns:
            df_filtered[['lat', 'long']] = df_filtered['geolocation'].str.split(',', expand=True)
            df_filtered['lat'] = pd.to_numeric(df_filtered['lat'], errors='coerce')
            df_filtered['long'] = pd.to_numeric(df_filtered['long'], errors='coerce')
        if 'lat' in df_filtered.columns and 'long' in df_filtered.columns:
            df_map = df_filtered.groupby(['lat', 'long', 'city']).agg(nb_projets=('id', 'nunique')).reset_index().dropna()
            fig_map = px.scatter_mapbox(df_map, lat='lat', lon='long', size='nb_projets', color='nb_projets',
                                        color_continuous_scale='Viridis', zoom=4, height=600,
                                        title="Carte des projets", hover_name='city')
            fig_map.update_layout(mapbox_style="open-street-map")
            st.plotly_chart(fig_map, use_container_width=True)
    with tab6:
        st.subheader("📊 Données brutes")
        st.dataframe(df_filtered, use_container_width=True)
        

