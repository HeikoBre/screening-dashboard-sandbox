import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import io
import base64
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle, HRFlowable, Bookmark
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas
import tempfile
import os

# Sidebar standardmäßig zugeklappt
st.set_page_config(initial_sidebar_state="collapsed")

# CSS
st.markdown("""
<style>
.main .block-container { font-size: 13px !important; }
h1 { font-size: 20px !important; }
h3 { font-size: 16px !important; }
h4 { font-size: 15px !important; }
.caption { font-size: 11px !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("# Expertenreview gNBS")

# Session State
if 'df' not in st.session_state: st.session_state.df = None
if 'genes' not in st.session_state: st.session_state.genes = []
if 'gene_dict' not in st.session_state: st.session_state.gene_dict = {}
if 'summary_df' not in st.session_state: st.session_state.summary_df = None
if 'total_responses' not in st.session_state: st.session_state.total_responses = 0
if 'user_comments' not in st.session_state: st.session_state.user_comments = {}

# Upload
if st.session_state.df is None:
    uploaded_file = st.file_uploader('CSV hochladen', type='csv')
    if uploaded_file is not None:
        with st.spinner('Lade & analysiere...'):
            df = pd.read_csv(uploaded_file, sep=',', quotechar='"', encoding='utf-8-sig', low_memory=False)
            st.session_state.df = df
            st.session_state.total_responses = len(df)
            
            # Namens-Extraktion
            gene_dict = {}
            for col in df.columns:
                if 'Gen: ' in col and 'Erkrankung: ' in col and 'nationalen' in col and '[Kommentar]' not in col:
                    gene_start = col.find('Gen: ') + 5
                    gene_end = col.find(' Erkrankung: ', gene_start)
                    gene = col[gene_start:gene_end].strip()
                    
                    disease_start = col.find('Erkrankung: ', gene_start) + 12
                    disease_end = col.find('"', disease_start) if '"' in col[disease_start:] else len(col)
                    disease = col[disease_start:disease_end].strip()
                    
                    if gene: gene_dict[gene] = disease
            
            st.session_state.genes = sorted(gene_dict.keys())
            st.session_state.gene_dict = gene_dict
            
            # Summary Tabelle (numerisch, Yes/No)
            summary_data = []
            options = ['Ja', 'Nein', 'Ich kann diese Frage nicht beantworten']
            for gene in st.session_state.genes:
                nat_q_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'nationalen' in col and '[Kommentar]' not in col]
                nat_kom_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'nationalen' in col and '[Kommentar]' in col]
                stud_q_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'wissenschaftlicher' in col and '[Kommentar]' not in col]
                stud_kom_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'wissenschaftlicher' in col and '[Kommentar]' in col]
                
                nat_data = df[nat_q_cols].stack().dropna()
                n_nat = len(nat_data)
                stud_data = df[stud_q_cols].stack().dropna()
                n_stud = len(stud_data)
                
                nat_ja = (nat_data == 'Ja').sum() / n_nat * 100 if n_nat > 0 else 0
                stud_ja = (stud_data == 'Ja').sum() / n_stud * 100 if n_stud > 0 else 0
                
                # Sammle Kommentare
                nat_comments = [str(c) for c in df[nat_kom_cols].stack().dropna() if str(c).strip()]
                stud_comments = [str(c) for c in df[stud_kom_cols].stack().dropna() if str(c).strip()]
                
                summary_data.append({
                    'Gen': gene,
                    'Erkrankung': st.session_state.gene_dict[gene],
                    'National_Ja_pct': round(nat_ja, 1),
                    'National_n': n_nat,
                    'Studie_Ja_pct': round(stud_ja, 1),
                    'Studie_n': n_stud,
                    'National_80': 'Yes' if nat_ja >= 80 else 'No',
                    'Kommentare_National': ' | '.join(nat_comments) if nat_comments else '',
                    'Kommentare_Studie': ' | '.join(stud_comments) if stud_comments else ''
                })
            
            st.session_state.summary_df = pd.DataFrame(summary_data)
            
        st.success(f'{len(st.session_state.genes)} Gene | {st.session_state.total_responses} Antworten')
        st.rerun()
else:
    if st.sidebar.button('Neue CSV 🗑️'): 
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# Funktion zum Generieren der CSV
def generate_csv():
    csv_buffer = io.StringIO()
    export_df = st.session_state.summary_df.copy()
    export_df.insert(0, 'Gesamt_Responses', st.session_state.total_responses)
    
    # User-Kommentare hinzufügen
    reviewer_comments = []
    for gene in export_df['Gen']:
        comment = st.session_state.user_comments.get(gene, '')
        reviewer_comments.append(comment)
    
    export_df['Reviewer_Kommentar'] = reviewer_comments
    
    export_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    return csv_buffer.getvalue().encode('utf-8-sig')

# Funktion zum Generieren des PDFs
def generate_pdf():
    """Generiert ein PDF-Dokument mit allen Genen, Visualisierungen und Kommentaren"""
    
    # Custom Canvas class für Footer mit Seitenzahlen
    class PageNumCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            canvas.Canvas.__init__(self, *args, **kwargs)
            self.pages = []
            self.creation_date = datetime.now().strftime('%d.%m.%Y')
            
        def showPage(self):
            self.pages.append(dict(self.__dict__))
            self._startPage()
            
        def save(self):
            page_count = len(self.pages)
            for page_num, page in enumerate(self.pages, start=1):
                self.__dict__.update(page)
                self.draw_page_number(page_num, page_count)
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)
            
        def draw_page_number(self, page_num, page_count):
            # Footer Linie
            self.setStrokeColor(colors.grey)
            self.setLineWidth(0.5)
            self.line(0.75*inch, 0.5*inch, A4[0] - 0.75*inch, 0.5*inch)
            
            # Footer Text
            self.setFont('Helvetica', 8)
            self.setFillColor(colors.grey)
            
            # Links: Datum
            self.drawString(0.75*inch, 0.35*inch, f"Erstellt am: {self.creation_date}")
            
            # Mitte: Seitenzahl
            page_text = f"Seite {page_num} von {page_count}"
            page_text_width = self.stringWidth(page_text, 'Helvetica', 8)
            center_x = (A4[0] - page_text_width) / 2
            self.drawString(center_x, 0.35*inch, page_text)
            
            # Rechts: UKHD Logo (falls vorhanden)
            try:
                # Logo-Pfad - entweder im gleichen Verzeichnis oder absoluter Pfad
                logo_path = "uk_akro.jpg"
                if os.path.exists(logo_path):
                    # Logo klein und dezent: 0.4 inch hoch
                    logo_height = 0.3*inch
                    logo_width = logo_height * 2  # Annahme: Logo ist etwa doppelt so breit wie hoch
                    
                    x_position = A4[0] - 0.75*inch - logo_width
                    y_position = 0.25*inch
                    
                    self.drawImage(logo_path, x_position, y_position, 
                                 width=logo_width, height=logo_height, 
                                 preserveAspectRatio=True, mask='auto')
            except Exception as e:
                # Falls Logo nicht gefunden wird, einfach weiter ohne Logo
                pass
    
    # Temporäre Datei für PDF
    pdf_buffer = io.BytesIO()
    
    # PDF Setup mit custom canvas
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    gene_style = ParagraphStyle(
        'GeneName',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2ca02c'),
        spaceAfter=6,
        spaceBefore=12
    )
    
    disease_style = ParagraphStyle(
        'DiseaseName',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.grey,
        spaceAfter=12,
        italic=True
    )
    
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#333333'),
        spaceAfter=8,
        spaceBefore=10
    )
    
    comment_style = ParagraphStyle(
        'CommentText',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=20,
        spaceAfter=6
    )
    
    story = []
    
    # Titelseite
    story.append(Paragraph("Expertenreview gNBS", title_style))
    story.append(Paragraph(f"Dokumentation vom {datetime.now().strftime('%d.%m.%Y')}", styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Gesamtanzahl Responses: {st.session_state.total_responses}", styles['Normal']))
    story.append(Paragraph(f"Anzahl Gene: {len(st.session_state.genes)}", styles['Normal']))
    story.append(PageBreak())
    
    # Inhaltsverzeichnis auf Seite 2
    story.append(Paragraph("Inhaltsverzeichnis", title_style))
    story.append(Spacer(1, 12))
    
    # TOC Style
    toc_style = ParagraphStyle(
        'TOCEntry',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        spaceAfter=4,
        textColor=colors.HexColor('#1f77b4')
    )
    
    # Erstelle TOC Einträge mit Links
    for idx, gene in enumerate(st.session_state.genes, start=1):
        disease = st.session_state.gene_dict.get(gene, '')
        # Verwende Bookmark-System von ReportLab
        toc_entry = Paragraph(f'<a href="#{gene}" color="blue"><b>{gene}</b> ({disease})</a>', toc_style)
        story.append(toc_entry)
    
    story.append(PageBreak())
    
    # Für jedes Gen eine Seite
    df = st.session_state.df
    
    for gene in st.session_state.genes:
        disease = st.session_state.gene_dict.get(gene, '')
        
        # Bookmark für Inhaltsverzeichnis-Links
        story.append(Bookmark(gene))
        
        # Gen-Header
        story.append(Paragraph(f"<b>{gene}</b>", gene_style))
        story.append(Paragraph(disease, disease_style))
        story.append(Spacer(1, 6))
        
        # Daten sammeln
        nat_q_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'nationalen' in col and '[Kommentar]' not in col]
        nat_kom_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'nationalen' in col and '[Kommentar]' in col]
        stud_q_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'wissenschaftlicher' in col and '[Kommentar]' not in col]
        stud_kom_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'wissenschaftlicher' in col and '[Kommentar]' in col]
        
        nat_data = df[nat_q_cols].stack().dropna()
        stud_data = df[stud_q_cols].stack().dropna()
        
        # Statistiken als Tabelle
        nat_ja = (nat_data == 'Ja').sum()
        nat_nein = (nat_data == 'Nein').sum()
        nat_na = (nat_data == 'Ich kann diese Frage nicht beantworten').sum()
        nat_total = len(nat_data)
        nat_ja_pct = (nat_ja / nat_total * 100) if nat_total > 0 else 0
        nat_nein_pct = (nat_nein / nat_total * 100) if nat_total > 0 else 0
        nat_na_pct = (nat_na / nat_total * 100) if nat_total > 0 else 0
        
        stud_ja = (stud_data == 'Ja').sum()
        stud_nein = (stud_data == 'Nein').sum()
        stud_na = (stud_data == 'Ich kann diese Frage nicht beantworten').sum()
        stud_total = len(stud_data)
        stud_ja_pct = (stud_ja / stud_total * 100) if stud_total > 0 else 0
        stud_nein_pct = (stud_nein / stud_total * 100) if stud_total > 0 else 0
        stud_na_pct = (stud_na / stud_total * 100) if stud_total > 0 else 0
        
        # Tabelle mit Ergebnissen
        data = [
            ['', 'Nationales Screening', 'Wissenschaftliche Studie'],
            ['Ja', f'{nat_ja} ({nat_ja_pct:.1f}%)', f'{stud_ja} ({stud_ja_pct:.1f}%)'],
            ['Nein', f'{nat_nein} ({nat_nein_pct:.1f}%)', f'{stud_nein} ({stud_nein_pct:.1f}%)'],
            ['Kann nicht beantworten', f'{nat_na} ({nat_na_pct:.1f}%)', f'{stud_na} ({stud_na_pct:.1f}%)'],
            ['Gesamt', f'n={nat_total}', f'n={stud_total}'],
            ['Cut-Off (≥80%)', '✓' if nat_ja_pct >= 80 else '✗', '✓' if stud_ja_pct >= 80 else '✗']
        ]
        
        t = Table(data, colWidths=[2.2*inch, 2*inch, 2*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#fafafa')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (1, 1), (-1, -2), [colors.white, colors.HexColor('#f9f9f9')]),
        ]))
        
        story.append(t)
        story.append(Spacer(1, 15))
        
        # Kommentare aus Umfrage - National
        nat_comments = [str(c) for c in df[nat_kom_cols].stack().dropna() if str(c).strip()]
        if nat_comments:
            story.append(Paragraph("<b>Kommentare National:</b>", section_style))
            for idx, comment in enumerate(nat_comments, 1):
                # Escape HTML characters in comments
                safe_comment = comment.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(f"{idx}. {safe_comment}", comment_style))
            story.append(Spacer(1, 10))
        
        # Kommentare aus Umfrage - Studie
        stud_comments = [str(c) for c in df[stud_kom_cols].stack().dropna() if str(c).strip()]
        if stud_comments:
            story.append(Paragraph("<b>Kommentare Studie:</b>", section_style))
            for idx, comment in enumerate(stud_comments, 1):
                safe_comment = comment.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(f"{idx}. {safe_comment}", comment_style))
            story.append(Spacer(1, 10))
        
        # Kommentare der Besprechung
        reviewer_comment = st.session_state.user_comments.get(gene, '')
        if reviewer_comment:
            story.append(Paragraph("<b>Kommentare der Besprechung:</b>", section_style))
            safe_reviewer_comment = reviewer_comment.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            # Splitze lange Kommentare in Absätze
            for para in safe_reviewer_comment.split('\n'):
                if para.strip():
                    story.append(Paragraph(para, comment_style))
            story.append(Spacer(1, 10))
        
        # Horizontaler Trennstrich
        story.append(Spacer(1, 5))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=10))
        
        # Gesamtbewertung mit Ampel-System (ganz unten)
        story.append(Paragraph(f"<b>Gesamtbewertung für <i>{gene}</i> ({disease}):</b>", section_style))
        
        # Ampel-Logik
        if nat_ja_pct >= 80:
            # GRÜN: National ≥80%
            ampel_color = colors.HexColor('#4CAF50')  # Grün
            ampel_text = "Aufnahme in nationales gNBS"
        elif stud_ja_pct >= 80:
            # GELB: National <80%, aber Studie ≥80%
            ampel_color = colors.HexColor('#FFC107')  # Gelb/Orange
            ampel_text = "Aufnahme in wissenschaftliche gNBS Studie"
        else:
            # ROT: Beide <80%
            ampel_color = colors.HexColor('#F44336')  # Rot
            ampel_text = "Keine Berücksichtigung der Zielerkrankung im Rahmen des gNBS"
        
        # Ampel-Box mit Hintergrundfarbe
        ampel_data = [[ampel_text]]
        ampel_table = Table(ampel_data, colWidths=[5*inch])
        ampel_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), ampel_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ROUNDEDCORNERS', [5, 5, 5, 5]),
        ]))
        
        story.append(ampel_table)
        story.append(Spacer(1, 15))
        
        # Seitenumbruch nach jedem Gen (außer beim letzten)
        if gene != st.session_state.genes[-1]:
            story.append(PageBreak())
    
    # PDF erstellen mit custom canvas
    doc.build(story, canvasmaker=PageNumCanvas)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()

# Sidebar Export
if st.session_state.summary_df is not None:
    st.sidebar.markdown("### 📥 Export")
    
    # Statistik über Kommentare
    num_comments = len([c for c in st.session_state.user_comments.values() if c.strip()])
    total_genes = len(st.session_state.genes)
    st.sidebar.caption(f"💬 {num_comments}/{total_genes} Gene kommentiert")
    
    # Zeige welche Gene kommentiert sind
    if st.session_state.user_comments:
        with st.sidebar.expander("📝 Kommentierte Gene"):
            for gene, comment in st.session_state.user_comments.items():
                if comment.strip():
                    st.sidebar.caption(f"✓ {gene}")
    
    today = datetime.now().strftime("%Y%m%d")
    
    # CSV Download
    st.sidebar.download_button(
        label=f'📊 CSV Zusammenfassung',
        data=generate_csv(),
        file_name=f'gNBS_Expertenreview_Zusammenfassung_{today}.csv',
        mime='text/csv',
        key='download_csv',
        use_container_width=True
    )
    
    # PDF Download
    st.sidebar.download_button(
        label=f'📄 PDF Dokumentation',
        data=generate_pdf(),
        file_name=f'gNBS_Expertenreview_Dokumentation_{today}.pdf',
        mime='application/pdf',
        key='download_pdf',
        use_container_width=True
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Gesamt:** {st.session_state.total_responses} Responses")
    
    # Vorschau mit Kommentar-Indikator
    preview_df = st.session_state.summary_df[['Gen', 'Erkrankung', 'National_Ja_pct', 'Studie_Ja_pct', 'National_80']].copy()
    preview_df['💬'] = preview_df['Gen'].apply(
        lambda gene: '✓' if st.session_state.user_comments.get(gene, '').strip() else ''
    )
    st.sidebar.dataframe(preview_df, use_container_width=True, height=300)

# Tabs (Visualisierung mit erweiterter Anzeige)
if st.session_state.df is not None:
    df = st.session_state.df
    tabs = st.tabs(st.session_state.genes)
    
    for tab_idx, tab in enumerate(tabs):
        with tab:
            gene = st.session_state.genes[tab_idx]
            disease = st.session_state.gene_dict.get(gene, '')
            
            col1, col2 = st.columns([1,3])
            with col1: st.markdown(f"**_{gene}_**")
            with col2: st.markdown(disease)
            
            # Vertikaler Strich unter Gen/Erkrankung mit reduziertem Abstand
            st.markdown("<hr style='margin-top: 5px; margin-bottom: 10px;'>", unsafe_allow_html=True)
            
            nat_q_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'nationalen' in col and '[Kommentar]' not in col]
            nat_kom_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'nationalen' in col and '[Kommentar]' in col]
            stud_q_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'wissenschaftlicher' in col and '[Kommentar]' not in col]
            stud_kom_cols = [col for col in df.columns if f'Gen: {gene}' in col and 'wissenschaftlicher' in col and '[Kommentar]' in col]

            options = ['Ja', 'Nein', 'Ich kann diese Frage nicht beantworten']
            
            # Hauptlayout: Links Abbildungen, Rechts Kommentarfeld
            viz_col, comment_col = st.columns([2, 1])
            
            with viz_col:
                left_col, right_col = st.columns(2)
                
                with left_col:
                    st.markdown("<h4 style='margin-top: 0px; margin-bottom: 10px;'>Nationales Screening</h4>", unsafe_allow_html=True)
                    nat_data = df[nat_q_cols].stack().dropna()
                    n_total = len(nat_data)
                    
                    # Pie Chart für National
                    colors_chart = ['#ACF3AE', '#C43D5A', '#DDDDDD']
                    labels = ['Ja', 'Nein', 'NA']
                    values = [
                        (nat_data == 'Ja').sum(),
                        (nat_data == 'Nein').sum(),
                        (nat_data == 'Ich kann diese Frage nicht beantworten').sum()
                    ]
                    
                    fig_nat = go.Figure(data=[go.Pie(
                        labels=labels,
                        values=values,
                        marker=dict(colors=colors_chart),
                        textinfo='percent',
                        textfont_size=12,
                        hole=0.5
                    )])
                    fig_nat.update_layout(
                        height=250,
                        margin=dict(t=0, b=0, l=0, r=0),
                        showlegend=False,
                        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                    )
                    st.plotly_chart(fig_nat, use_container_width=True, key=f'nat_viz_{gene}_{tab_idx}')
                    
                    # Erweiterte Anzeige
                    ja_count = (nat_data == 'Ja').sum()
                    nein_count = (nat_data == 'Nein').sum()
                    weiss_nicht_count = (nat_data == 'Ich kann diese Frage nicht beantworten').sum()
                    ja_pct = ja_count / n_total * 100 if n_total > 0 else 0
                    
                    st.caption(f'**Gesamt:** n={n_total}')
                    st.caption(f'Ja: {ja_count} | Nein: {nein_count} | NA: {weiss_nicht_count}')
                    st.caption(f'Cut-Off: {"✅ ≥80%" if ja_pct >= 80 else "❌ <80%"}')

                with right_col:
                    st.markdown("<h4 style='margin-top: 0px; margin-bottom: 10px;'>Wissenschaftliche Studie</h4>", unsafe_allow_html=True)
                    stud_data = df[stud_q_cols].stack().dropna()
                    n_total_stud = len(stud_data)
                    
                    # Pie Chart für Studie
                    values_stud = [
                        (stud_data == 'Ja').sum(),
                        (stud_data == 'Nein').sum(),
                        (stud_data == 'Ich kann diese Frage nicht beantworten').sum()
                    ]
                    
                    fig_stud = go.Figure(data=[go.Pie(
                        labels=labels,
                        values=values_stud,
                        marker=dict(colors=colors_chart),
                        textinfo='percent',
                        textfont_size=12,
                        hole=0.5
                    )])
                    fig_stud.update_layout(
                        height=250,
                        margin=dict(t=0, b=0, l=0, r=0),
                        showlegend=False,
                        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                    )
                    st.plotly_chart(fig_stud, use_container_width=True, key=f'stud_viz_{gene}_{tab_idx}')
                    
                    # Erweiterte Anzeige
                    ja_count_stud = (stud_data == 'Ja').sum()
                    nein_count_stud = (stud_data == 'Nein').sum()
                    weiss_nicht_count_stud = (stud_data == 'Ich kann diese Frage nicht beantworten').sum()
                    ja_pct_stud = ja_count_stud / n_total_stud * 100 if n_total_stud > 0 else 0
                    
                    st.caption(f'**Gesamt:** n={n_total_stud}')
                    st.caption(f'Ja: {ja_count_stud} | Nein: {nein_count_stud} | NA: {weiss_nicht_count_stud}')
                    st.caption(f'Cut-Off: {"✅ ≥80%" if ja_pct_stud >= 80 else "❌ <80%"}')

                # Legende direkt unter den Abbildungen
                st.markdown("""
                <div style='background-color: transparent; padding: 8px; border-radius: 5px; margin-top: 10px; margin-bottom: 15px; border: 1px solid #e0e0e0;'>
                    <span style='font-size: 12px; font-weight: 600;'>Legende:</span>
                    <span style='background-color: #ACF3AE; padding: 2px 8px; border-radius: 3px; margin-left: 10px; font-size: 11px;'>Ja</span>
                    <span style='background-color: #C43D5A; color: white; padding: 2px 8px; border-radius: 3px; margin-left: 5px; font-size: 11px;'>Nein</span>
                    <span style='background-color: #DDDDDD; padding: 2px 8px; border-radius: 3px; margin-left: 5px; font-size: 11px;'>Kann ich nicht beantworten</span>
                </div>
                """, unsafe_allow_html=True)

            # Rechte Spalte: Kommentarfeld mit vertikaler Trennlinie
            with comment_col:
                st.markdown("""
                <div style='border-left: 3px solid #4CAF50; padding-left: 15px; margin-left: 10px;'>
                """, unsafe_allow_html=True)
                
                st.markdown("<h4 style='margin-top: 0px; margin-bottom: 10px;'>Notizen</h4>", unsafe_allow_html=True)
                
                # Hole den aktuellen Kommentar
                current_comment = st.session_state.user_comments.get(gene, '')
                
                user_comment = st.text_area(
                    f"_{gene}_",
                    value=current_comment,
                    height=300,
                    key=f'comment_input_{gene}_{tab_idx}',
                    placeholder="Hier können Sie Ihre Anmerkungen, Bewertungen oder Entscheidungen zu diesem Gen dokumentieren...",
                    label_visibility="collapsed"
                )
                
                col_save, col_clear = st.columns(2)
                with col_save:
                    if st.button('💾 Speichern', key=f'save_{gene}_{tab_idx}', use_container_width=True):
                        st.session_state.user_comments[gene] = user_comment
                        st.rerun()
                with col_clear:
                    if st.button('🗑️ Löschen', key=f'clear_{gene}_{tab_idx}', use_container_width=True):
                        st.session_state.user_comments[gene] = ''
                        st.rerun()
                
                if gene in st.session_state.user_comments and st.session_state.user_comments[gene]:
                    st.caption(f'💬 Gespeichert: {len(st.session_state.user_comments[gene])} Zeichen')
                
                st.markdown("</div>", unsafe_allow_html=True)

            # Kommentare mit Expander (standardmäßig ausgeklappt)
            st.markdown("<h4 style='font-size: 17px; margin-top: 20px;'>Kommentare aus Umfrage</h4>", unsafe_allow_html=True)
            nat_comments = [str(c) for c in df[nat_kom_cols].stack().dropna() if str(c).strip()]
            stud_comments = [str(c) for c in df[stud_kom_cols].stack().dropna() if str(c).strip()]
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**National:** ({len(nat_comments)} Kommentare)")
                if nat_comments:
                    with st.expander(f"Alle {len(nat_comments)} Kommentare anzeigen", expanded=True):
                        for idx, c in enumerate(nat_comments, 1):
                            st.caption(f"{idx}. {c}")
                else:
                    st.caption("Keine Kommentare")
                    
            with c2:
                st.markdown(f"**Studie:** ({len(stud_comments)} Kommentare)")
                if stud_comments:
                    with st.expander(f"Alle {len(stud_comments)} Kommentare anzeigen", expanded=True):
                        for idx, c in enumerate(stud_comments, 1):
                            st.caption(f"{idx}. {c}")
                else:
                    st.caption("Keine Kommentare")
