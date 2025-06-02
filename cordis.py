import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ⚙️ Configuration de la page
st.set_page_config(layout="wide", page_title="Dashboard CORDIS")
st.title("📊 Tableau de bord des projets financés par CORDIS")
st.caption("⚠️ Chargement en cours, merci de patienter 🙏")

# 📂 Choix du fichier source
dataset_choice = st.sidebar.radio(
    "📁 Choix du dataset :",
    [
        "CORDIS - Organismes financés par EU/FR",
        "CORDIS - Base Total"
    ],
    index=0
)

@st.cache_data
def load_data(path):
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip().str.lower()
    return df

with st.spinner("Chargement des données..."):
    filepath = (
        r"jointure_resultat.xlsx"
        if dataset_choice == "CORDIS - Organismes financés par EU/FR"
        else r"cleanbasefinal_with_keywords_v2_virgule_separe.xlsx"
    )
    df = load_data(filepath)

st.success(f"✅ Dataset chargé : {dataset_choice}")

# Prétraitement
for date_col in ['startdate', 'enddate']:
    df[date_col] = pd.to_datetime(df.get(date_col), errors='coerce')
df['startyear'] = df['startdate'].dt.year
for col in ['totalcost_project', 'ecmaxcontribution', 'eccontribution', 'neteccontribution']:
    if col in df.columns:
        df[col] = pd.to_numeric(
            df[col].astype(str)
                  .str.replace('.', '', regex=False)
                  .str.replace(',', '.', regex=False),
            errors='coerce'
        )

# 🧰 Filtres dynamiques
st.sidebar.header("🎯 Filtres")
filters = {}
for col, label in [
    ('status', 'Statut'),
    ('year', 'Année'),
    ('role', 'Rôle'),
    ('legalbasis', 'Cadre légal'),
    ('name', 'Organisation'),
    ('city', 'Ville'),
    ('acronym', 'Acronyme'),
    ('categorie_principale', 'Catégorie scientifique'),
    ('sous_categorie', 'Sous-catégorie')
]:
    if col == 'year':
        opts = sorted(df['startyear'].dropna().unique())
    elif col in df.columns:
        opts = sorted(df[col].dropna().unique())
    else:
        continue
    filters[col] = st.sidebar.multiselect(label, opts)

# 🔍 Application des filtres
df_filtered = df.copy()
for k, v in filters.items():
    if v:
        key = 'startyear' if k == 'year' else k
        df_filtered = df_filtered[df_filtered[key].isin(v)]

# 📊 Agrégation des projets
df_proj = (
    df_filtered
    .groupby('id', as_index=False)
    .agg(
        title=('title', 'first'),
        totalcost=('totalcost_project', 'first'),
        ecmax=('ecmaxcontribution', 'first'),
        startdate=('startdate', 'min'),
        enddate=('enddate', 'max')
    )
)
df_proj['startyear'] = df_proj['startdate'].dt.year
if 1 == 1:
    st.title("📊 Tableau de bord CORDIS 2014-2023")

    # KPIs
    st.subheader("🔢 Indicateurs clés")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nombre projets", df_proj['title'].nunique())
    col2.metric("Financement UE (€)", f"{df_proj['ecmax'].sum():,.0f}")
    col3.metric("Coût total (€)", f"{df_proj['totalcost'].sum():,.0f}")
    if 'keywords' in df.columns:
        pct_na = df_filtered['keywords'].isna().mean() * 100
        col4.metric("% sans mots-clés", f"{pct_na:.1f}%")

def compute_cagr(start, end, n):
    return ((end/start)**(1/n)-1)*100 if start > 0 and n > 0 else np.nan

# 🗂️ Création des onglets (NO résumé tab!)
tabs = st.tabs([
    "📈 Financement par année",
    "📊 Évolution catégories",
    "🏢 Top organisations",
    "📊 Statuts",
    "📊 Rôles",
    "🌍 Carte des projets",
    "🔑 Mots-clés & Catégories",
    "📊 Données brutes"
])

# [0] Financement par année
with tabs[0]:
    df_year_cat = (
        df_filtered
        .groupby(['startyear', 'categorie_principale'], as_index=False)
        .ecmaxcontribution.sum()
        .rename(columns={'ecmaxcontribution': 'total_funding'})
    )
    years = sorted(df_year_cat['startyear'].unique())
    y0 = st.selectbox("Année début", years, index=0, key="y0")
    y1 = st.selectbox("Année fin", years, index=len(years)-1, key="y1")
    df_bar = df_year_cat[df_year_cat['startyear'].between(y0, y1)].copy()
    df_bar['pct'] = df_bar.groupby('startyear')['total_funding'].transform(lambda x: x / x.sum() * 100)
    fig1 = px.bar(df_bar, x='startyear', y='total_funding', color='categorie_principale',
                  text=df_bar['pct'].round(1).astype(str)+'%', barmode='stack', template='plotly_white',
                  labels={'startyear': 'Année', 'total_funding': 'Financement (€)', 'categorie_principale': 'Catégorie'})
    fig1.update_layout(legend=dict(orientation='h', y=1.02, x=1), bargap=0.2)
    st.plotly_chart(fig1, use_container_width=True)
    # Insight
    if not df_bar.empty:
        ly = df_bar['startyear'].max()
        top = df_bar[df_bar['startyear'] == ly].nlargest(1, 'total_funding').iloc[0]
        st.markdown(
    f"ℹ️ **Insight** : De **{y0} à {y1}**, la catégorie la plus financée est **{top['categorie_principale']}** avec **{top['total_funding']:,.0f} €**."
    "<br/><span style='font-size: 0.95em; color: #888;'>"
    "Utilisez les filtres “Année début” et “Année fin” ci-dessus pour modifier la période analysée."
    "</span>",
    unsafe_allow_html=True
)

# [1] Évolution catégories
with tabs[1]:
      st.subheader("📊 Répartition des projets par année")

    # On part de df_proj (chaque 'id' de projet est unique) pour compter par année de début
    df_count_year = (
        df_proj
        .groupby('startyear', as_index=False)
        .agg(nb_projets=('id', 'nunique'))
        .dropna(subset=['startyear'])
        .sort_values('startyear')
    )

    # Graphique en barres du nombre de projets par année
    fig_year = px.bar(
        df_count_year,
        x='startyear',
        y='nb_projets',
        text='nb_projets',
        template='plotly_white',
        labels={'startyear': 'Année de début', 'nb_projets': 'Nombre de projets'},
        title="Nombre de projets financés par année"
    )
    fig_year.update_traces(textposition="outside")
    fig_year.update_layout(
        xaxis=dict(dtick=1),
        yaxis=dict(title="Nombre de projets"),
        bargap=0.2
    )
    st.plotly_chart(fig_year, use_container_width=True)

    # Insight : année ayant le plus de projets
    if not df_count_year.empty:
        annee_max = int(df_count_year.loc[df_count_year['nb_projets'].idxmax(), 'startyear'])
        nb_max = int(df_count_year['nb_projets'].max())
        st.markdown(
            f"ℹ️ **Insight** : L'année avec le plus grand nombre de projets est "
            f"**{annee_max}** avec **{nb_max}** projets."
        )
    st.subheader("📈 Évolution des catégories principales")

    df_year_cat = (
        df_filtered
        .groupby(['startyear', 'categorie_principale'], as_index=False)
        .ecmaxcontribution.sum()
        .rename(columns={'ecmaxcontribution': 'total_funding'})
    )
    years = sorted(df_year_cat['startyear'].unique())
    l0 = st.selectbox("Année début", years, index=0, key="l0")
    l1 = st.selectbox("Année fin", years, index=len(years)-1, key="l1")

    df_line_sel = df_year_cat[df_year_cat['startyear'].between(l0, l1)]

    # Sélecteur de catégorie principale pour filtrer les sous-catégories
    all_categories = sorted(df_line_sel['categorie_principale'].dropna().unique())
    selected_cats = st.multiselect("Filtrer par catégorie principale :", all_categories, default=all_categories)

    # Filtrage du graphique 1
    df_line_sel = df_line_sel[df_line_sel['categorie_principale'].isin(selected_cats)]

    fig2 = px.line(df_line_sel, x='startyear', y='total_funding', color='categorie_principale',
                   markers=True, template='plotly_white',
                   labels={'startyear': 'Année', 'total_funding': 'Financement (€)', 'categorie_principale': 'Catégorie'})
    fig2.update_layout(legend=dict(orientation='h', y=1.02, x=1))
    st.plotly_chart(fig2, use_container_width=True)

    # Insight croissance principales
    pivot = df_line_sel.pivot(index='categorie_principale', columns='startyear', values='total_funding').fillna(0)
    pivot['growth'] = pivot.get(l1, 0) - pivot.get(l0, 0)
    top3 = pivot['growth'].nlargest(3)
    st.markdown(f"🔍 **Top 3 croissances ({l0}→{l1})** : " + ", ".join([f"{cat} (+{val:,.0f} €)" for cat, val in top3.items()]))

    # Évolution sous-catégories
    st.subheader("📉 Évolution des sous-catégories")

    df_souscat = (
        df_filtered
        .groupby(['startyear', 'categorie_principale', 'sous_categorie'], as_index=False)
        .agg(total_funding=('ecmaxcontribution', 'sum'))
        .dropna(subset=['sous_categorie'])
    )
    df_souscat_sel = df_souscat[
        (df_souscat['startyear'].between(l0, l1)) &
        (df_souscat['categorie_principale'].isin(selected_cats))
    ]

    fig2b = px.line(
        df_souscat_sel,
        x='startyear',
        y='total_funding',
        color='sous_categorie',
        markers=True,
        template='plotly_white',
        labels={
            'startyear': 'Année',
            'total_funding': 'Financement (€)',
            'sous_categorie': 'Sous-catégorie'
        }
    )
    fig2b.update_layout(legend=dict(orientation='h', y=1.1, x=0))
    st.plotly_chart(fig2b, use_container_width=True)

    # Insight croissance sous-catégories
    pivot_souscat = df_souscat_sel.pivot(index='sous_categorie', columns='startyear', values='total_funding').fillna(0)
    pivot_souscat['growth'] = pivot_souscat.get(l1, 0) - pivot_souscat.get(l0, 0)
    top3_souscat = pivot_souscat['growth'].nlargest(3)

    st.markdown("🔍 **Top 3 croissances sous-catégories** : " + ", ".join([f"{cat} (+{val:,.0f} €)" for cat, val in top3_souscat.items()]))

# [2] Top organisations
with tabs[2]:
    df_org = df_filtered.groupby(['name', 'city'], as_index=False).ecmaxcontribution.sum().rename(columns={'ecmaxcontribution': 'total'})
    fig3 = px.bar(df_org.nlargest(10, 'total'), x='total', y='name', orientation='h', text='total',
                  color='total', hover_data=['city'], template='plotly_white',
                  labels={'total': 'Financement (€)', 'name': 'Organisation'})
    fig3.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig3, use_container_width=True)
    if not df_org.empty:
        top_org = df_org.nlargest(1, 'total').iloc[0]
        st.markdown(f"ℹ️ **Insight** : L'organisation la mieux financée est **{top_org['name']}** ({top_org['total']:,.0f} €) basée à {top_org['city']}.")

# [3] Statuts
with tabs[3]:
    if 'status' in df_filtered.columns:
        df_stat = df_filtered.drop_duplicates('id')['status'].value_counts().reset_index(name='count').rename(columns={'index': 'status'})
        fig4 = px.pie(df_stat, names='status', values='count', title='Répartition des statuts', template='plotly_white')
        st.plotly_chart(fig4, use_container_width=True)
        # Insight
        top_status = df_stat.nlargest(1, 'count').iloc[0]
        st.markdown(f"ℹ️ **Insight** : Le statut le plus fréquent est **{top_status['status']}** avec {top_status['count']} projets.")

# [4] Rôles
with tabs[4]:
    if 'role' in df_filtered.columns:
        df_role = df_filtered.drop_duplicates(['id', 'role'])['role'].value_counts().reset_index(name='count').rename(columns={'index': 'role'})
        fig5 = px.pie(df_role, names='role', values='count', title='Répartition des rôles', template='plotly_white')
        st.plotly_chart(fig5, use_container_width=True)
        top_role = df_role.nlargest(1, 'count').iloc[0]
        st.markdown(f"ℹ️ **Insight** : Le rôle prédominant est **{top_role['role']}** dans {top_role['count']} projets.")

# [5] Carte des projets
with tabs[5]:
    if 'geolocation' in df_filtered.columns:
        coords = df_filtered['geolocation'].str.split(',', expand=True)
        df_filtered['lat'] = pd.to_numeric(coords[0], errors='coerce')
        df_filtered['lon'] = pd.to_numeric(coords[1], errors='coerce')
        df_map = df_filtered.dropna(subset=['lat', 'lon']).groupby('city', as_index=False).agg(nb=('id', 'nunique'), lat=('lat', 'first'), lon=('lon', 'first'))
        fig6 = px.scatter_mapbox(df_map, lat='lat', lon='lon', size='nb', color='nb',
                                 hover_name='city', zoom=4, height=500, template='plotly_white')
        fig6.update_layout(mapbox_style='open-street-map')
        st.plotly_chart(fig6, use_container_width=True)
        top_city = df_map.nlargest(1, 'nb').iloc[0]
        st.markdown(f"ℹ️ **Insight** : La ville avec le plus de projets est **{top_city['city']}** ({top_city['nb']} projets).")

# [6] Mots-clés & Catégories
with tabs[6]:
    st.subheader('🔑 Mots-clés')
    if 'keywords' in df_filtered.columns:
        kws = df_filtered['keywords'].dropna().str.split(r'[;,]').explode().str.strip()
        top10 = kws.value_counts().head(10).rename_axis('kw').reset_index(name='count')
        fig7 = px.bar(top10, x='count', y='kw', orientation='h', template='plotly_white', labels={'count': 'Occurrences', 'kw': 'Mot-clé'})
        st.plotly_chart(fig7, use_container_width=True)
        st.markdown(f"ℹ️ **Insight** : Le mot-clé le plus fréquent est **{top10.iloc[0]['kw']}** ({top10.iloc[0]['count']} occurrences).")
    st.subheader('🔬 Catégories scientifiques')
    df_cat = df_filtered['categorie_principale'].value_counts().head(10).rename_axis('cat').reset_index(name='count')
    st.bar_chart(df_cat.set_index('cat')['count'])

# [7] Données brutes
with tabs[7]:
    st.subheader('📊 Données brutes')
    st.write(df_filtered.select_dtypes(include=[np.number]).describe().T)
    st.write("**Filtres actifs :**", {k: v for k, v in filters.items() if v})
    st.download_button("Télécharger CSV", data=df_filtered.to_csv(index=False).encode('utf-8'), file_name="cordis_filtered.csv", mime="text/csv")
