import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import io
import base64
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle, HRFlowable
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

/* Verbesserte Tab-Navigation */
[data-baseweb="tab-list"] {
    gap: 4px;
    background-color: #f8f9fa;
    padding: 8px;
    border-radius: 8px;
}

[data-baseweb="tab"] {
    border-radius: 6px;
    padding: 8px 16px;
    background-color: white;
    border: 1px solid #e0e0e0;
    font-size: 13px;
    transition: all 0.2s ease;
}

[data-baseweb="tab"]:hover {
    background-color: #f0f0f0;
    border-color: #4CAF50;
}

[aria-selected="true"][data-baseweb="tab"] {
    background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
    color: white !important;
    border: 2px solid #3d8b40;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(76, 175, 80, 0.3);
    transform: translateY(-1px);
}

[aria-selected="true"][data-baseweb="tab"] p {
    color: white !important;
}
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
if 'gene_decisions' not in st.session_state: st.session_state.gene_decisions = {}  # Neu: Dropdown-Entscheidungen

# Upload
if st.session_state.df is None:
    uploaded_file = st.file_uploader('CSV hochladen', type='csv')
    if uploaded_file is not None:
        with st.spinner('Lade & analysiere...'):
            # Versuche verschiedene Encoding-Optionen und lade ALLE Spalten
            try:
                df = pd.read_csv(uploaded_file, sep=',', quotechar='"', encoding='utf-8-sig', 
                               low_memory=False, engine='python')
            except:
                uploaded_file.seek(0)
                try:
                    df = pd.read_csv(uploaded_file, sep=',', quotechar='"', encoding='utf-8', 
                                   low_memory=False, engine='python')
                except:
                    uploaded_file.seek(0)
                    try:
                        df = pd.read_csv(uploaded_file, sep=',', quotechar='"', encoding='latin-1', 
                                       low_memory=False, engine='python')
                    except:
                        uploaded_file.seek(0)
                        # Letzte Option: c engine ohne low_memory
                        df = pd.read_csv(uploaded_file, sep=',', quotechar='"', encoding='utf-8-sig')
            
            st.session_state.df = df
            st.session_state.total_responses = len(df)
            
            # Namens-Extraktion - berücksichtigt auch Non-Breaking Spaces
            gene_dict = {}
            matching_columns = []
            all_gene_columns = []
            
            # Debug-Counter
            has_gen = 0
            has_erkrankung = 0
            has_nationalen = 0
            has_all_without_kommentar = 0
            
            # Sammle ALLE Spalten die "Gen: " enthalten
            for col in df.columns:
                if 'Gen:' in col:  # Ohne Leerzeichen, um auch "Gen:\xa0" zu matchen
                    all_gene_columns.append(col)
                    has_gen += 1
                    
                    # Prüfe auf Erkrankung (mit normalem Leerzeichen ODER Non-Breaking Space)
                    if 'Erkrankung:' in col:  # Ohne Leerzeichen danach
                        has_erkrankung += 1
                        
                        if 'nationalen' in col:
                            has_nationalen += 1
                            
                            if '[Kommentar]' not in col:
                                has_all_without_kommentar += 1
                                matching_columns.append(col)
                                
                                # Gen extrahieren
                                gene_start = col.find('Gen:') + 4
                                # Überspringe Leerzeichen (normal oder NBSP)
                                while gene_start < len(col) and col[gene_start] in ' \xa0\t':
                                    gene_start += 1
                                    
                                # Suche nach "Erkrankung:"
                                gene_end = col.find('Erkrankung:', gene_start)
                                if gene_end == -1:
                                    continue
                                    
                                gene = col[gene_start:gene_end].strip(' \xa0\t')
                                
                                # Erkrankung extrahieren
                                disease_start = col.find('Erkrankung:', gene_start) + 11
                                # Überspringe Leerzeichen (normal oder NBSP)
                                while disease_start < len(col) and col[disease_start] in ' \xa0\t':
                                    disease_start += 1
                                    
                                # Finde Ende (vor [Kommentar] oder am Ende)
                                disease_end = len(col)
                                for marker in [' [', '\n', '\t', '  ']:
                                    pos = col.find(marker, disease_start)
                                    if pos != -1 and pos < disease_end:
                                        disease_end = pos
                                        
                                disease = col[disease_start:disease_end].strip(' \xa0\t')
                                
                                if gene: 
                                    gene_dict[gene] = disease
            
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
            
        st.success(f'✅ {len(st.session_state.genes)} Gene | {st.session_state.total_responses} Antworten')
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
    
    # Entscheidungen hinzufügen
    decisions = []
    for gene in export_df['Gen']:
        decision = st.session_state.gene_decisions.get(gene, 'Noch nicht bewertet')
        decisions.append(decision)
    export_df['Empfehlung'] = decisions
    
    # User-Kommentare hinzufügen
    reviewer_comments = []
    for gene in export_df['Gen']:
        comment = st.session_state.user_comments.get(gene, '')
        reviewer_comments.append(comment)
    
    export_df['Zusaetzliche_Notizen'] = reviewer_comments
    
    export_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    return csv_buffer.getvalue().encode('utf-8-sig')

# Funktion zum Generieren des PDFs
def generate_pdf():
    """Generiert ein PDF-Dokument mit allen Genen, Visualisierungen und Kommentaren"""
    
    # Custom Canvas class für Footer mit Seitenzahlen und Bookmarks
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
            
            # Mitte: Seitenzahl - mit mehr Platz für zweistellige Zahlen
            page_text = f"Seite {page_num} von {page_count}"
            page_text_width = self.stringWidth(page_text, 'Helvetica', 8)
            center_x = (A4[0] - page_text_width) / 2
            # Stelle sicher dass genug Platz für den Text ist
            if center_x < 0.75*inch + 100:  # Mindestabstand zum linken Text
                center_x = 0.75*inch + 100
            self.drawString(center_x, 0.35*inch, page_text)
            
            # Rechts: UKHD Logo (falls vorhanden)
            try:
                logo_path = "uk_akro.jpg"
                if os.path.exists(logo_path):
                    logo_height = 0.4*inch
                    logo_width = logo_height * 2
                    x_position = A4[0] - 0.5*inch - logo_width
                    y_position = 0.25*inch
                    self.drawImage(logo_path, x_position, y_position, 
                                 width=logo_width, height=logo_height, 
                                 preserveAspectRatio=True, mask='auto')
            except Exception as e:
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
    
    toc_style = ParagraphStyle(
        'TOCEntry',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        spaceAfter=6,
        textColor=colors.HexColor('#1f77b4')
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
    
    # Erstelle TOC Einträge - wir berechnen die Seitenzahlen
    # Seite 1 = Titel, Seite 2 = TOC, ab Seite 3 = Gene
    for idx, gene in enumerate(st.session_state.genes):
        disease = st.session_state.gene_dict.get(gene, '')
        page_num = idx + 3  # Start bei Seite 3
        
        # Erstelle TOC Zeile
        toc_text = f'<b>{gene}</b> ({disease})'
        
        # Tabelle für TOC-Zeile (Text links, Seitenzahl rechts)
        # Verwende Paragraph nur für den Gen-Namen, nicht für die Seitenzahl
        toc_data = [[Paragraph(toc_text, toc_style), str(page_num)]]
        toc_table = Table(toc_data, colWidths=[5.5*inch, 0.5*inch])
        toc_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica'),
            ('FONTSIZE', (1, 0), (1, 0), 10),
            ('TEXTCOLOR', (1, 0), (1, 0), colors.HexColor('#1f77b4')),
        ]))
        story.append(toc_table)
    
    story.append(PageBreak())
    
    # Für jedes Gen eine Seite
    df = st.session_state.df
    
    for gene in st.session_state.genes:
        disease = st.session_state.gene_dict.get(gene, '')
        
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
        
        # Empfehlung der Besprechung (prominent anzeigen)
        decision = st.session_state.gene_decisions.get(gene, 'Noch nicht bewertet')
        if decision and decision != 'Noch nicht bewertet':
            story.append(Paragraph("<b>Empfehlung der Expertengruppe:</b>", section_style))
            
            # Entferne Emoji für PDF
            decision_text = decision.replace('🟢 ', '').replace('🟡 ', '').replace('🔴 ', '').replace('⚪ ', '')
            
            # Farbe basierend auf Empfehlung
            if 'nationales gNBS' in decision:
                box_color = colors.HexColor('#4CAF50')
            elif 'wissenschaftliche' in decision:
                box_color = colors.HexColor('#FFC107')
            elif 'Keine Berücksichtigung' in decision:
                box_color = colors.HexColor('#F44336')
            else:
                box_color = colors.HexColor('#9E9E9E')
            
            decision_data = [[decision_text]]
            decision_table = Table(decision_data, colWidths=[5.5*inch])
            decision_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), box_color),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('ROUNDEDCORNERS', [5, 5, 5, 5]),
            ]))
            story.append(decision_table)
            story.append(Spacer(1, 15))
        
        # Kommentare aus Umfrage - National
        nat_comments = [str(c) for c in df[nat_kom_cols].stack().dropna() if str(c).strip()]
        if nat_comments:
            story.append(Paragraph("<b>Kommentare National:</b>", section_style))
            for idx, comment in enumerate(nat_comments, 1):
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
        
        # Zusätzliche Notizen der Besprechung
        reviewer_comment = st.session_state.user_comments.get(gene, '')
        if reviewer_comment:
            story.append(Paragraph("<b>Zusätzliche Notizen:</b>", section_style))
            safe_reviewer_comment = reviewer_comment.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            for para in safe_reviewer_comment.split('\n'):
                if para.strip():
                    story.append(Paragraph(para, comment_style))
            story.append(Spacer(1, 10))
        
        # Horizontaler Trennstrich
        story.append(Spacer(1, 5))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=10))
        
        # Zeige Hinweis wenn keine Empfehlung gegeben wurde
        if not decision or decision == 'Noch nicht bewertet':
            story.append(Paragraph(f"<b>Automatische Bewertung basierend auf Umfrageergebnissen:</b>", section_style))
            
            # Ampel-Logik nur als Vorschlag wenn keine manuelle Entscheidung getroffen wurde
            if nat_ja_pct >= 80:
                ampel_color = colors.HexColor('#E8F5E9')
                text_color = colors.HexColor('#2E7D32')
                ampel_text = "Vorschlag: Aufnahme in nationales gNBS (≥80% Zustimmung national)"
            elif stud_ja_pct >= 80:
                ampel_color = colors.HexColor('#FFF8E1')
                text_color = colors.HexColor('#F57F17')
                ampel_text = "Vorschlag: Aufnahme in wissenschaftliche gNBS Studie (≥80% Zustimmung Studie)"
            else:
                ampel_color = colors.HexColor('#FFEBEE')
                text_color = colors.HexColor('#C62828')
                ampel_text = "Vorschlag: Keine Berücksichtigung im gNBS (<80% Zustimmung)"
            
            # Hellere Box für Vorschläge
            ampel_data = [[ampel_text]]
            ampel_table = Table(ampel_data, colWidths=[5.5*inch])
            ampel_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), ampel_color),
                ('TEXTCOLOR', (0, 0), (-1, -1), text_color),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('ROUNDEDCORNERS', [5, 5, 5, 5]),
            ]))
            
            story.append(ampel_table)
            story.append(Spacer(1, 10))
        
        story.append(Spacer(1, 5))
        
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
    
    # Statistik über Bewertungen
    num_decided = len([d for d in st.session_state.gene_decisions.values() if d and d != 'Noch nicht bewertet'])
    num_comments = len([c for c in st.session_state.user_comments.values() if c.strip()])
    total_genes = len(st.session_state.genes)
    st.sidebar.caption(f"✅ {num_decided}/{total_genes} Gene bewertet")
    st.sidebar.caption(f"💬 {num_comments}/{total_genes} Gene mit Notizen")
    
    # Zeige welche Gene bewertet sind
    if st.session_state.gene_decisions:
        with st.sidebar.expander("📋 Bewertete Gene"):
            for gene, decision in st.session_state.gene_decisions.items():
                if decision and decision != 'Noch nicht bewertet':
                    # Emoji extrahieren
                    emoji = decision.split(' ')[0] if decision.split(' ')[0] in ['🟢', '🟡', '🔴', '⚪'] else '✓'
                    st.sidebar.caption(f"{emoji} {gene}")
    
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
    
    # Fortschrittsanzeige mit visueller Gen-Übersicht
    num_decided = len([d for d in st.session_state.gene_decisions.values() if d and d != 'Noch nicht bewertet'])
    total_genes = len(st.session_state.genes)
    progress_pct = num_decided / total_genes if total_genes > 0 else 0
    
    # Kompakte visuelle Übersicht
    st.markdown(f"""
    <div style='background-color: #fafafa; padding: 8px 15px; border-radius: 6px; margin-bottom: 12px; border: 1px solid #e8e8e8;'>
        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;'>
            <span style='font-weight: 500; color: #555; font-size: 12px;'>Bewertungsfortschritt</span>
            <span style='color: #777; font-size: 11px;'>{num_decided} von {total_genes} ({progress_pct*100:.0f}%)</span>
        </div>
        <div style='background-color: #e8e8e8; height: 6px; border-radius: 3px; overflow: hidden;'>
            <div style='background: linear-gradient(90deg, #4CAF50 0%, #45a049 100%); 
                        height: 100%; 
                        width: {progress_pct*100}%;
                        transition: width 0.3s ease;'></div>
        </div>
        <div style='display: flex; gap: 3px; margin-top: 8px; flex-wrap: wrap;'>
            {''.join([f"<span style='background-color: {'#4CAF50' if st.session_state.gene_decisions.get(gene, '') and st.session_state.gene_decisions.get(gene, '') != 'Noch nicht bewertet' else '#ddd'}; width: 6px; height: 6px; border-radius: 50%; display: inline-block;' title='{gene}: {st.session_state.gene_decisions.get(gene, 'Nicht bewertet')}'></span>" for gene in st.session_state.genes])}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    tabs = st.tabs(st.session_state.genes)
    
    for tab_idx, tab in enumerate(tabs):
        with tab:
            gene = st.session_state.genes[tab_idx]
            disease = st.session_state.gene_dict.get(gene, '')
            
            # Visueller Header mit Hervorhebung
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #e8f5e9 0%, #f1f8f4 100%); 
                        padding: 15px 20px; 
                        border-radius: 10px; 
                        border-left: 5px solid #4CAF50;
                        margin-bottom: 20px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.05);'>
                <div style='display: flex; align-items: center; gap: 15px;'>
                    <div style='background: #4CAF50; 
                                color: white; 
                                padding: 8px 15px; 
                                border-radius: 6px; 
                                font-weight: 700;
                                font-size: 16px;'>
                        {gene}
                    </div>
                    <div style='flex: 1; color: #666; font-size: 14px;'>
                        {disease}
                    </div>
                    <div style='color: #999; font-size: 12px; font-weight: 500;'>
                        Gen {tab_idx + 1} von {len(st.session_state.genes)}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
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

            # Rechte Spalte: Bewertung und optionales Kommentarfeld
            with comment_col:
                st.markdown("""
                <div style='border-left: 3px solid #4CAF50; padding-left: 15px; margin-left: 10px;'>
                """, unsafe_allow_html=True)
                
                st.markdown("<h4 style='margin-top: 0px; margin-bottom: 10px;'>Bewertung</h4>", unsafe_allow_html=True)
                
                # Dropdown für Empfehlung
                decision_options = [
                    'Noch nicht bewertet',
                    '🟢 Aufnahme in nationales gNBS',
                    '🟡 Aufnahme in wissenschaftliche gNBS Studie', 
                    '🔴 Keine Berücksichtigung im gNBS',
                    '⚪ Weitere Diskussion erforderlich'
                ]
                
                current_decision = st.session_state.gene_decisions.get(gene, 'Noch nicht bewertet')
                
                decision = st.selectbox(
                    'Empfehlung',
                    options=decision_options,
                    index=decision_options.index(current_decision) if current_decision in decision_options else 0,
                    key=f'decision_{gene}_{tab_idx}',
                    label_visibility='collapsed'
                )
                
                # Speichere Entscheidung automatisch
                if decision != current_decision:
                    st.session_state.gene_decisions[gene] = decision
                    st.rerun()
                
                st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                
                # Optionales Kommentarfeld
                with st.expander("💬 Zusätzliche Notizen (optional)", expanded=bool(st.session_state.user_comments.get(gene, '').strip())):
                    current_comment = st.session_state.user_comments.get(gene, '')
                    
                    user_comment = st.text_area(
                        f"Notizen_{gene}",
                        value=current_comment,
                        height=200,
                        key=f'comment_input_{gene}_{tab_idx}',
                        placeholder="Hier können Sie zusätzliche Anmerkungen, Begründungen oder Diskussionspunkte dokumentieren...",
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
                
                # Zeige aktuelle Bewertung
                if decision != 'Noch nicht bewertet':
                    st.markdown(f"""
                    <div style='margin-top: 15px; padding: 10px; background-color: #f0f7f0; border-radius: 6px; border-left: 3px solid #4CAF50;'>
                        <div style='font-size: 11px; color: #666; margin-bottom: 4px;'>Aktuelle Bewertung:</div>
                        <div style='font-size: 13px; font-weight: 600; color: #333;'>{decision}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
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
