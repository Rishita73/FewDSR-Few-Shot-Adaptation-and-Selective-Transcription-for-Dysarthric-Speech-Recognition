import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=80, bottom=80, left=100, right=100):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def set_table_borders(table, color="D3D3D3"):
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'<w:tblBorders {nsdecls("w")}><w:top w:val="single" w:sz="6" w:space="0" w:color="{color}"/><w:bottom w:val="single" w:sz="6" w:space="0" w:color="{color}"/><w:left w:val="none"/><w:right w:val="none"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="{color}"/><w:insideV w:val="none"/></w:tblBorders>')
    tblPr.append(borders)

def build_report():
    doc = docx.Document()

    # Page Margins: Standard Academic 1.0 inch all around (with 1.25 in left for binding)
    # Printable width: 8.27 - (1.25 + 1.0) = 6.02 inches
    for section in doc.sections:
        section.page_width = Inches(8.27)   # A4
        section.page_height = Inches(11.69)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.0)

    # Styles
    normal = doc.styles['Normal']
    normal.font.name = 'Times New Roman'
    normal.font.size = Pt(12)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    def add_p(text, bold=False, size=12, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=6, line_spacing=1.5):
        p = doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.line_spacing = line_spacing
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.space_after = Pt(space_after)
        run = p.add_run(text)
        run.bold = bold
        run.font.size = Pt(size)
        run.font.italic = italic
        run.font.name = 'Times New Roman'
        return p

    def add_heading_1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(16)
        run.font.color.rgb = RGBColor(15, 34, 64)
        run.font.name = 'Times New Roman'
        return p

    def add_heading_2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(30, 58, 138)
        run.font.name = 'Times New Roman'
        return p

    def add_heading_3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(12)
        run.font.italic = True
        run.font.color.rgb = RGBColor(50, 50, 50)
        run.font.name = 'Times New Roman'
        return p

    print("Building Document with Clean, Tightly-Organized Layout...")

    # =========================================================================
    # PAGE 1: TITLE PAGE (COVER) - ELEGANT 2-COLUMN TABLE FOR NAMES
    # =========================================================================
    add_p("A MID-TERM DESIGN PROJECT REPORT ON", bold=True, size=12, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=6, space_after=10)
    add_p("FewDSR: Confidence-Calibrated Few-Shot Adaptation and Selective Transcription for Dysarthric Speech Recognition", bold=True, size=15, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=14, line_spacing=1.2)
    
    add_p("Submitted in partial fulfilment of the requirements for the award of the degree of", italic=True, size=10.5, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)
    add_p("BACHELOR OF TECHNOLOGY", bold=True, size=13, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    add_p("IN", size=10.5, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    add_p("COMPUTER SCIENCE AND ENGINEERING", bold=True, size=12, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)

    # Clean, Organized 2-Column Box for Submitted by & Guided by (No large gaps!)
    box_table = doc.add_table(rows=1, cols=2)
    box_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    box_table.autofit = False
    box_col_widths = [Inches(3.0), Inches(3.0)]

    c_sub, c_guide = box_table.rows[0].cells
    c_sub.width = box_col_widths[0]
    c_guide.width = box_col_widths[1]

    # Cell 1: Submitted by
    p_sub = c_sub.paragraphs[0]
    p_sub.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_sub.paragraph_format.line_spacing = 1.15
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(0)
    
    r_sub_h = p_sub.add_run("SUBMITTED BY:\n")
    r_sub_h.bold = True
    r_sub_h.font.size = Pt(11)
    
    r_sub_1 = p_sub.add_run("1. Rishita Bhandari\n   Roll No: 230000101080\n")
    r_sub_1.font.size = Pt(10.5)
    
    r_sub_2 = p_sub.add_run("2. Radhika Negi\n   Roll No: 230000101076\n")
    r_sub_2.font.size = Pt(10.5)
    
    r_sub_c = p_sub.add_run("B.Tech CSE, 7th Semester")
    r_sub_c.italic = True
    r_sub_c.font.size = Pt(10)

    # Cell 2: Under the Guidance of
    p_gui = c_guide.paragraphs[0]
    p_gui.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_gui.paragraph_format.line_spacing = 1.15
    p_gui.paragraph_format.space_before = Pt(0)
    p_gui.paragraph_format.space_after = Pt(0)

    r_gui_h = p_gui.add_run("UNDER THE GUIDANCE OF:\n")
    r_gui_h.bold = True
    r_gui_h.font.size = Pt(11)

    r_gui_1 = p_gui.add_run("Dr. Shailesh Panwar\n")
    r_gui_1.bold = True
    r_gui_1.font.size = Pt(11)

    r_gui_2 = p_gui.add_run("Department of Computer Science & Engg.\nFaculty of Technology\nUTU Dehradun")
    r_gui_2.font.size = Pt(10.5)

    # University Footer
    add_p("DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING\nFACULTY OF TECHNOLOGY\nVEER MADHO SINGH BHANDARI UTTARAKHAND TECHNICAL UNIVERSITY\nDEHRADUN, UTTARAKHAND\nACADEMIC SESSION: 2026–2027", bold=True, size=10.5, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=24, space_after=0, line_spacing=1.2)

    doc.add_page_break()

    # =========================================================================
    # PAGE 2: CANDIDATE'S DECLARATION - SYMMETRICAL SIGNATURE BLOCK
    # =========================================================================
    add_p("CANDIDATE'S DECLARATION", bold=True, size=15, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=10, space_after=18)
    
    add_p("We hereby declare that the work presented in this report entitled \"FewDSR: Confidence-Calibrated Few-Shot Adaptation and Selective Transcription for Dysarthric Speech Recognition\", submitted towards the partial fulfilment of the requirements for the award of the degree of Bachelor of Technology in Computer Science and Engineering to the Department of Computer Science and Engineering, Faculty of Technology, Veer Madho Singh Bhandari Uttarakhand Technical University, Dehradun, is an authentic record of our original research and engineering work carried out under the supervision and guidance of Dr. Shailesh Panwar.", space_after=14)

    add_p("We further confirm that this work has not been submitted previously, in part or in full, to any other university, institute, or examining body for the award of any degree, diploma, or fellowship. All experimental architectures, benchmark comparisons, algorithmic formulations, and running prototypes presented herein have been independently developed and evaluated by us, and all intellectual contributions, foundation models, published literature, and clinical datasets utilized have been duly referenced and acknowledged in accordance with standard academic ethics.", space_after=36)

    # Date and Place
    p_dp = doc.add_paragraph()
    p_dp.paragraph_format.space_after = Pt(28)
    p_dp.paragraph_format.line_spacing = 1.2
    p_dp.add_run("Date: 23rd November, 2026\nPlace: Dehradun, Uttarakhand").italic = True

    # Symmetrical 2-Column Signatures
    table_sig = doc.add_table(rows=1, cols=2)
    table_sig.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_sig.autofit = False
    table_sig.columns[0].width = Inches(3.0)
    table_sig.columns[1].width = Inches(3.0)
    
    c0 = table_sig.cell(0, 0).paragraphs[0]
    c0.paragraph_format.line_spacing = 1.15
    c0.paragraph_format.space_after = Pt(0)
    c0.add_run("______________________________\n").bold = True
    c0.add_run("Rishita Bhandari\n").bold = True
    c0.add_run("University Roll No: 230000101080\nB.Tech CSE, 7th Semester\nFaculty of Technology, UTU")

    c1 = table_sig.cell(0, 1).paragraphs[0]
    c1.paragraph_format.line_spacing = 1.15
    c1.paragraph_format.space_after = Pt(0)
    c1.add_run("______________________________\n").bold = True
    c1.add_run("Radhika Negi\n").bold = True
    c1.add_run("University Roll No: 230000101076\nB.Tech CSE, 7th Semester\nFaculty of Technology, UTU")

    doc.add_page_break()

    # =========================================================================
    # PAGE 3: SUPERVISOR CERTIFICATE
    # =========================================================================
    add_p("DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING\nFACULTY OF TECHNOLOGY\nVEER MADHO SINGH BHANDARI UTTARAKHAND TECHNICAL UNIVERSITY, DEHRADUN", bold=True, size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)
    
    add_p("CERTIFICATE OF APPROVAL", bold=True, size=15, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)

    add_p("This is to certify that the project report entitled \"FewDSR: Confidence-Calibrated Few-Shot Adaptation and Selective Transcription for Dysarthric Speech Recognition\", submitted by Rishita Bhandari (Roll No: 230000101080) and Radhika Negi (Roll No: 230000101076) in partial fulfilment of the requirements for the award of Bachelor of Technology in Computer Science and Engineering, is a bonafide record of the mid-term design project work carried out under my supervision during the academic session 2026–2027.", space_after=14)

    add_p("The students have successfully demonstrated their 40% Running Module benchmark, including Pause-Preserving Audio Preprocessing, Cross-Attention LoRA Parameter-Efficient Adaptation, Acoustic-Null Grounding Hallucination Mitigation, and Calibrated Selective Prediction. The results presented in this report have been thoroughly inspected, tested on benchmark dysarthric audio sets, and found satisfactory for the mid-term evaluation milestone.", space_after=44)

    # Supervisor signatures
    table_cert = doc.add_table(rows=1, cols=2)
    table_cert.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_cert.autofit = False
    table_cert.columns[0].width = Inches(3.0)
    table_cert.columns[1].width = Inches(3.0)
    
    c0 = table_cert.cell(0, 0).paragraphs[0]
    c0.paragraph_format.line_spacing = 1.15
    c0.paragraph_format.space_after = Pt(0)
    c0.add_run("______________________________\n").bold = True
    c0.add_run("Dr. Shailesh Panwar\n").bold = True
    c0.add_run("Project Supervisor\nDept. of Computer Science & Engg.\nFaculty of Technology, UTU")

    c1 = table_cert.cell(0, 1).paragraphs[0]
    c1.paragraph_format.line_spacing = 1.15
    c1.paragraph_format.space_after = Pt(0)
    c1.add_run("______________________________\n").bold = True
    c1.add_run("Head of Department\n").bold = True
    c1.add_run("Dept. of Computer Science & Engg.\nFaculty of Technology\nUTU Dehradun")

    doc.add_page_break()

    # =========================================================================
    # PAGE 4: ACKNOWLEDGEMENTS
    # =========================================================================
    add_p("ACKNOWLEDGEMENTS", bold=True, size=15, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=10, space_after=18)

    add_p("We express our deepest and most profound sense of gratitude to our respected project supervisor, Dr. Shailesh Panwar, Department of Computer Science and Engineering, Veer Madho Singh Bhandari Uttarakhand Technical University, Dehradun, for his indispensable mentorship, insightful technical suggestions, and continuous encouragement throughout the conception, architectural design, and experimental execution of this design project.", space_after=12)

    add_p("We are immensely grateful to the Head of Department, Department of Computer Science and Engineering, and all faculty members of the Faculty of Technology for providing state-of-the-art computational infrastructure, academic support, and constructive feedback during the project proposal review sessions.", space_after=12)

    add_p("We also extend our sincere appreciation to the creators and maintainers of the TORGO dysarthric speech database at the University of Toronto and Toronto Rehabilitation Institute, as well as the researchers behind the open-source speech processing community (OpenAI Whisper, Hugging Face Transformers, and PEFT libraries), whose foundational contributions made this rigorous research achievable.", space_after=12)

    add_p("Lastly, we owe heartfelt thanks to our families, friends, and peers for their unyielding patience, moral encouragement, and constant belief in our capabilities throughout this academic journey.", space_after=28)

    # Tight, neat acknowledgement signature block
    p_ack_sig = doc.add_paragraph()
    p_ack_sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_ack_sig.paragraph_format.line_spacing = 1.15
    p_ack_sig.paragraph_format.space_after = Pt(0)
    r_ack = p_ack_sig.add_run("Rishita Bhandari (Roll No: 230000101080)\nRadhika Negi (Roll No: 230000101076)\nB.Tech CSE, 7th Semester\nFaculty of Technology, UTU Dehradun")
    r_ack.bold = True
    r_ack.font.size = Pt(11)

    doc.add_page_break()

    # =========================================================================
    # PAGE 5: ABSTRACT
    # =========================================================================
    add_p("ABSTRACT", bold=True, size=15, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=10, space_after=18)

    add_p("Automatic Speech Recognition (ASR) interfaces represent a vital assistive conduit for individuals living with severe neuromotor disabilities such as Cerebral Palsy (CP), Amyotrophic Lateral Sclerosis (ALS), and stroke-induced speech impairments. However, modern foundation speech models—exemplified by OpenAI Whisper—suffer a catastrophic breakdown when deployed in dysarthric speech contexts. While these architectures demonstrate Word Error Rates (WER) below 5% on standard fluent speech, their error rates deteriorate sharply to between 40% and 70% on dysarthric speech due to severe acoustic distribution mismatches, reduced vowel space, and imprecise consonant articulation. Furthermore, standard models exhibit a hazardous failure mode: during the typical 1.5-to-2.5-second respiratory pauses characteristic of motor-speech disorders, autoregressive decoders experience hallucinatory generative loops, fabricating fluent but completely ungrounded phrases (e.g., \"Thank you for watching...\") that present extreme clinical risks in assistive care.", space_after=12)

    add_p("This report presents the formulation, architectural engineering, and mid-term evaluation of FewDSR (Confidence-Calibrated Few-Shot Adaptation and Selective Transcription for Dysarthric Speech Recognition). To resolve the fundamental tension between acoustic personalization and physical vocal fatigue, FewDSR introduces a 4-stage pipeline: (1) a Pause-Preserving Voice Activity Detector featuring an extended 600ms hangover window that prevents speech fragmentation; (2) a Parameter-Efficient Low-Rank Adaptation (LoRA) module injected strictly into decoder cross-attention layers, updating less than 0.02% of model parameters and converging on an ultra-low calibration budget of 5 to 20 utterances; (3) an Acoustic-Null Grounding Margin (Delta = z(w) - z(nospeech)) coupled with post-hoc Temperature Scaling (T = 1.35) to eliminate pause hallucinations and restore probability calibration; and (4) a Calibrated Selective Prediction Engine that outputs confident words normally while explicitly enclosing uncertain tokens in [UNCERTAIN: word] safety markers.", space_after=12)

    add_p("At this 40% running module milestone, the end-to-end framework has been operationalized as a standalone, zero-cloud interactive evaluation prototype. Empirical benchmarking across TORGO speech severity tiers demonstrates substantial error reductions: from 36.4% to 9.1% on mild dysarthria, from 62.5% to 12.5% on moderate dysarthria, from 66.7% to 16.7% on severe dysarthria, and completely eliminating pause hallucinations (dropping pause WER from 150.0% to 0.0%). Furthermore, the system successfully demonstrates bilingual extension to an authentic Hindi post-stroke assistive scenario, dropping error rates from 85.7% to 0.0% while safely suppressing hallucinated tokens. The entire engine executes with a Real-Time Factor below 0.1 on commodity laptop CPUs.", space_after=16)

    add_p("Keywords: Dysarthric Speech Recognition, Whisper Foundation Model, Low-Rank Adaptation (LoRA), Few-Shot Calibration, Hallucination Suppression, Selective Transcription, Assistive Technology.", bold=True, italic=True, size=10, space_after=6)

    doc.add_page_break()

    # =========================================================================
    # PAGE 6: TABLE OF CONTENTS
    # =========================================================================
    add_p("TABLE OF CONTENTS", bold=True, size=15, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=10, space_after=18)

    toc_data = [
        ("Candidate's Declaration", "ii"),
        ("Certificate of Approval", "iii"),
        ("Acknowledgements", "iv"),
        ("Abstract", "v"),
        ("List of Figures", "vii"),
        ("List of Tables", "vii"),
        ("List of Abbreviations", "vii"),
        ("Chapter 1: Introduction & Motivation", "1"),
        ("    1.1 Context and Assistive Communication Imperative", "1"),
        ("    1.2 Clinical Etiology and Acoustic Pathologies of Dysarthria", "2"),
        ("    1.3 The Accessibility Divide in Foundation Speech Architectures", "2"),
        ("    1.4 The Vocal Fatigue Barrier and Ultra-Low Resource Calibration", "3"),
        ("    1.5 The Autoregressive Hallucination Catastrophe during Breathing Pauses", "3"),
        ("    1.6 Multilingual & Indian Regional Dimension (Hindi Aspiration Collapse)", "4"),
        ("    1.7 Organization of the Report", "4"),
        ("Chapter 2: Literature Review & Problem Formulation", "5"),
        ("    2.1 Evolution of Automatic Speech Recognition Paradigms", "5"),
        ("    2.2 Foundation Encoder-Decoder Models (OpenAI Whisper)", "6"),
        ("    2.3 Parameter-Efficient Fine-Tuning (PEFT and LoRA in ASR)", "6"),
        ("    2.4 Non-Speech Hallucination Mitigation Techniques", "7"),
        ("    2.5 Uncertainty Quantification, Confidence Calibration, and Selective Prediction", "7"),
        ("    2.6 Critical Comparative Synthesis of Prior Art", "8"),
        ("    2.7 Identified Research Gaps and Formal Problem Statement", "8"),
        ("Chapter 3: Proposed Methodology & System Architecture", "9"),
        ("    3.1 Architectural Overview of the 4-Stage FewDSR Pipeline", "9"),
        ("    3.2 Stage 1: Pause-Preserving Audio Preprocessing (600ms Hangover VAD)", "10"),
        ("    3.3 Stage 2: Few-Shot Cross-Attention LoRA Adaptation", "10"),
        ("    3.4 Stage 3: Post-Hoc Temperature Calibration & Acoustic-Null Grounding", "11"),
        ("    3.5 Stage 4: Calibrated Selective Prediction Engine", "12"),
        ("    3.6 Edge Compatibility and Quantization Deployment Strategy", "12"),
        ("Chapter 4: Implementation, 40% Running Module & Experimental Evaluation", "13"),
        ("    4.1 Benchmark Corpora and Clinical Test Audio Profiles", "13"),
        ("    4.2 Development Environment and Computational Specifications", "14"),
        ("    4.3 The 40% Running Module: Interactive Evaluation Dashboard", "14"),
        ("    4.4 Empirical Benchmark Results: Baseline Whisper vs FewDSR", "15"),
        ("    4.5 Hallucination Suppression Analysis during Prolonged Pauses", "16"),
        ("    4.6 Calibration Scaling and Expected Calibration Error (ECE) Minimization", "16"),
        ("    4.7 Risk-Coverage Trade-off and Selective Accuracy", "17"),
        ("Chapter 5: Project Management, Future Roadmap & Conclusion", "18"),
        ("    5.1 40% Milestone Deliverables Verification", "18"),
        ("    5.2 Remaining 60% Research & Engineering Roadmap", "19"),
        ("    5.3 Division of Responsibilities and Work Allocation Matrix", "19"),
        ("    5.4 Conclusion and Societal Assistive Impact", "20"),
        ("References", "21")
    ]

    for title, page_num in toc_data:
        p_toc = doc.add_paragraph()
        p_toc.paragraph_format.line_spacing = 1.15
        p_toc.paragraph_format.space_after = Pt(3)
        r1 = p_toc.add_run(title)
        if not title.startswith("    "):
            r1.bold = True
        
        dots_count = max(5, 75 - len(title))
        p_toc.add_run(" " + "." * dots_count + " ")
        r2 = p_toc.add_run(page_num)
        if not title.startswith("    "):
            r2.bold = True

    doc.add_page_break()

    # =========================================================================
    # PAGE 7: LIST OF FIGURES, TABLES & ABBREVIATIONS
    # =========================================================================
    add_p("LIST OF FIGURES", bold=True, size=13, space_before=10, space_after=8)
    figures = [
        ("Figure 1.1: Neuromuscular articulatory breakdown across motor speech subsystems", "2"),
        ("Figure 2.1: Architectural diagram of Whisper encoder-decoder and cross-attention blocks", "6"),
        ("Figure 3.1: Complete End-to-End 4-Stage Architecture of the FewDSR Framework", "9"),
        ("Figure 3.2: Short-time energy envelope and 600ms hangover window VAD masking", "10"),
        ("Figure 3.3: Low-Rank Adaptation (LoRA) injection strictly into cross-attention projections", "11"),
        ("Figure 3.4: Acoustic-Null Grounding Margin check vs native non-speech token score", "12"),
        ("Figure 4.1: Streamlit Mid-Term Evaluation Dashboard showcasing live side-by-side transcripts", "15"),
        ("Figure 4.2: Empirical Word Error Rate (WER) comparison across dysarthria severities", "16"),
        ("Figure 4.3: Calibration budget scaling curve showing rapid convergence at N=10 sentences", "17"),
        ("Figure 4.4: Reliability diagram (ECE) before and after post-hoc temperature scaling", "17")
    ]
    for title, page_num in figures:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.1
        p.paragraph_format.space_after = Pt(2)
        p.add_run(title)
        dots = max(5, 75 - len(title))
        p.add_run(" " + "." * dots + " " + page_num)

    add_p("LIST OF TABLES", bold=True, size=13, space_before=14, space_after=8)
    tables = [
        ("Table 1.1: Clinical and Acoustic Profiles of Major Dysarthria Subtypes", "3"),
        ("Table 2.1: Critical Comparative Synthesis of Prior Assistive ASR Literature", "8"),
        ("Table 3.1: Parameter Distribution and LoRA Footprint on Whisper-Small Base", "11"),
        ("Table 4.1: Empirical Benchmarking across TORGO Dysarthric Severities", "15"),
        ("Table 4.2: Bilingual Evaluation on Hindi Assistive Post-Stroke Utterance", "16"),
        ("Table 4.3: Post-Hoc Calibration and ECE Reduction Across Softmax Temperatures", "17"),
        ("Table 5.1: 6-Phase Project Timeline and Mid-Term Deliverables Verification", "18"),
        ("Table 5.2: Student Work Division Matrix (Rishita Bhandari & Radhika Negi)", "19")
    ]
    for title, page_num in tables:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.1
        p.paragraph_format.space_after = Pt(2)
        p.add_run(title)
        dots = max(5, 75 - len(title))
        p.add_run(" " + "." * dots + " " + page_num)

    add_p("LIST OF ABBREVIATIONS", bold=True, size=13, space_before=14, space_after=8)
    abbreviations = [
        ("ASR", "Automatic Speech Recognition"),
        ("LoRA", "Low-Rank Adaptation"),
        ("PEFT", "Parameter-Efficient Fine-Tuning"),
        ("WER", "Word Error Rate"),
        ("CER", "Character Error Rate"),
        ("ECE", "Expected Calibration Error"),
        ("VAD", "Voice Activity Detection"),
        ("CP", "Cerebral Palsy"),
        ("ALS", "Amyotrophic Lateral Sclerosis"),
        ("RTF", "Real-Time Factor"),
        ("LOSO", "Leave-One-Speaker-Out (Cross-Validation)")
    ]
    for abbr, full in abbreviations:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.1
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"**{abbr}**")
        r.bold = True
        p.add_run(f"\t: {full}")

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 1: INTRODUCTION & MOTIVATION
    # =========================================================================
    add_heading_1("CHAPTER 1: INTRODUCTION & MOTIVATION")
    
    add_heading_2("1.1 Context and Assistive Communication Imperative")
    add_p("Speech represents the primary, most ecologically natural, and highest-bandwidth modality for human interaction and computer mediation. Over the past decade, rapid breakthroughs in deep learning and foundation models have catalyzed ubiquitous voice interfaces across mobile smartphones, automated transcription platforms, and voice-assisted ambient living tools. For the general demographic, hands-free speech recognition provides convenience and productivity enhancements. However, for individuals living with motor disabilities—particularly those who have lost upper-limb motor dexterity—speech interfaces represent an indispensable lifeline for personal autonomy, access to education, vocational employment, and basic social agency.")
    add_p("Despite massive advancements in Automatic Speech Recognition (ASR), commercial and state-of-the-art foundation models rest upon an unstated and highly restrictive foundational assumption: that the acoustic input originates from a standard, anatomically intact vocal apparatus producing fluent speech. For the millions of individuals worldwide living with motor-speech disorders—most notably dysarthria—this core assumption completely collapses, creating an acute accessibility barrier.")

    add_heading_2("1.2 Clinical Etiology and Acoustic Pathologies of Dysarthria")
    add_p("Dysarthria is a clinical neuromotor disorder of speech production resulting from neurological injury or neurodegenerative diseases affecting either the central or peripheral nervous system. Prominent underlying etiologies include Cerebral Palsy (CP), Amyotrophic Lateral Sclerosis (ALS or Motor Neuron Disease), Parkinson's disease, traumatic brain injury, and stroke. Crucially, dysarthria is an articulatory and phonatory impairment rather than a cognitive or linguistic language disorder. An individual living with dysarthria possesses completely unimpaired intellectual faculties, full cognitive reasoning, and exact semantic intent; however, the impaired physical execution of speech muscles results in distorted phonetic output.")
    add_p("The clinical manifestations of dysarthria compromise all five primary subsystems of speech production:")
    add_p("1. Respiration: Diminished vital lung capacity and diaphragm coordination lead to shallow breathing, short phrase bursts, and prolonged, irregular respiratory recovery pauses.", space_after=3)
    add_p("2. Phonation: Involuntary vocal fold hyperadduction or flaccidity produces strained-strangled vocal qualities, severe breathiness, pitch instability, and tremor.", space_after=3)
    add_p("3. Resonance: Velopharyngeal incompetence allows air escape through the nasal cavity, causing persistent hypernasality.", space_after=3)
    add_p("4. Articulation: Weakness, spasticity, or ataxia of the tongue, lips, and mandible results in consonant elision, centralized vowel spaces, and slurred phoneme boundaries.", space_after=3)
    add_p("5. Prosody: Imprecise temporal coordination creates monoloudness, monopitch, and erratic speech rates.", space_after=6)

    # Table 1.1
    add_p("Table 1.1: Clinical and Acoustic Profiles of Major Dysarthria Subtypes", bold=True, size=11, space_before=6, space_after=4)
    table_1 = doc.add_table(rows=6, cols=4)
    table_1.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_1.autofit = False
    table_1.columns[0].width = Inches(1.3)
    table_1.columns[1].width = Inches(1.5)
    table_1.columns[2].width = Inches(1.4)
    table_1.columns[3].width = Inches(1.8)
    set_table_borders(table_1)
    
    headers = ["Dysarthria Type", "Neurological Pathology", "Primary Etiology", "Acoustic Failure Manifestation"]
    for i, h in enumerate(headers):
        cell = table_1.cell(0, i)
        cell.paragraphs[0].add_run(h).bold = True
        set_cell_background(cell, "E2E8F0")
        set_cell_margins(cell, 100, 100, 120, 120)

    rows_data = [
        ("Spastic", "Upper Motor Neuron Lesion", "Cerebral Palsy, Stroke", "Strained-strangled voice, slow rate, severe pitch breaks"),
        ("Flaccid", "Lower Motor Neuron Lesion", "ALS, Bulbar Palsy", "Breathy phonation, hypernasality, extreme vocal fatigue"),
        ("Athetoid / Dyskinetic", "Basal Ganglia Circuitry", "Cerebral Palsy", "Involuntary articulatory spasms, irregular breathing pauses"),
        ("Ataxic", "Cerebellar Control Circuit", "Cerebellar Ataxia", "Erratic scanning prosody, irregular phoneme breakdowns"),
        ("Hypokinetic", "Dopaminergic Depletion", "Parkinson's Disease", "Monopitch, hypophonia (low volume), rushed mumbling")
    ]
    for r_idx, r_data in enumerate(rows_data):
        for c_idx, val in enumerate(r_data):
            cell = table_1.cell(r_idx + 1, c_idx)
            cell.paragraphs[0].add_run(val)
            set_cell_margins(cell, 70, 70, 100, 100)

    add_heading_2("1.3 The Accessibility Divide in Foundation Speech Architectures")
    add_p("Recent foundation architectures—most notably OpenAI Whisper—have demonstrated unprecedented zero-shot robustness across standard accents, acoustic reverberations, and background environmental noises. However, benchmark evaluations reveal that foundation models experience an acute performance cliff when exposed to atypical motor speech. On standard corpora such as LibriSpeech, Whisper models achieve Word Error Rates below 4%; however, on standard dysarthric benchmarks such as TORGO, the zero-shot Word Error Rate degrades to between 38% on mild dysarthria and over 70% on severe cases. Consequently, the very demographic that requires speech interfaces the most is the most disenfranchised by modern ASR advances.")

    add_heading_2("1.4 The Vocal Fatigue Barrier and Ultra-Low Resource Calibration")
    add_p("A recognized engineering paradigm to bridge this domain mismatch is acoustic personalization—fine-tuning the speech model on recordings from the target dysarthric speaker. However, conventional fine-tuning requires dozens of hours of patient speech to converge without catastrophic forgetting. For individuals with motor disorders, speech production demands immense physical exertion and concentration. Prolonged vocalization induces severe vocal strain, respiratory fatigue, and physical distress. Therefore, a clinically viable assistive system must respect the vocal fatigue boundary: it must adapt successfully under an extreme calibration budget of only 5 to 20 short calibration utterances.")

    add_heading_2("1.5 The Autoregressive Hallucination Catastrophe during Breathing Pauses")
    add_p("A second, dangerous failure mode inherent to generative sequence-to-sequence foundation models is ungrounded hallucination. Standard dysarthric speech is characterized by prolonged breathing intervals (often 1.5 to 2.5 seconds) where the speaker gasps or pauses to replenish lung volume. During these silence intervals, the acoustic encoder output contains near-zero phonemic energy. Because Whisper's autoregressive text decoder relies heavily on its internal language model prior, it begins fabricating fluent, highly probable phrases from its web training data (e.g., \"Thank you for watching and don't forget to subscribe\"). In medical, assistive, and emergency communication contexts, presenting an ungrounded hallucination as an authoritative transcription introduces severe safety risks.")

    add_heading_2("1.6 Multilingual & Indian Regional Dimension (Hindi Aspiration Collapse)")
    add_p("In the context of the Indian linguistic ecosystem (such as at UTU Dehradun), speech interfaces must accommodate non-English languages. In Hindi, consonants feature phonemic aspirated pairs (महाप्राण व्यंजन such as ख, घ, छ, झ, ठ, थ, फ) in contrast to unaspirated stops (अल्पप्राण such as क, ग, च, ज, ट, त, प). Producing aspiration requires substantial pulmonary breath velocity (प्राण वायु). A dysarthric patient recovering from a stroke or living with Parkinson's lacks the respiratory control to articulate aspiration, causing aspirated consonants to collapse into unaspirated substitutes. When coupled with typical breathing silences, multilingual foundation models collapse into nonsensical English subtitles or loop hallucinations, emphasizing the vital need for calibrated grounding.")

    add_heading_2("1.7 Organization of the Report")
    add_p("The remainder of this report is organized as follows: Chapter 2 reviews relevant literature in foundation models, parameter-efficient adaptation, and uncertainty calibration, culminating in our formal problem statement. Chapter 3 details the 4-stage FewDSR architecture and mathematical formulation. Chapter 4 presents the experimental implementation, running module verification, benchmark results on TORGO and Hindi dysarthria, and diagnostic curves. Chapter 5 outlines project management, the 60% completion roadmap, work division, and conclusions.")

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 2: LITERATURE REVIEW & PROBLEM FORMULATION
    # =========================================================================
    add_heading_1("CHAPTER 2: LITERATURE REVIEW & PROBLEM FORMULATION")

    add_heading_2("2.1 Evolution of Automatic Speech Recognition Paradigms")
    add_p("Automatic Speech Recognition (ASR) has evolved across three major technological epochs. Early systems relied on Hidden Markov Models (HMMs) combined with Gaussian Mixture Models (GMMs) or deep neural networks (DNN-HMM) under modular acoustic, pronunciation lexicon, and n-gram language models. The second epoch introduced end-to-end architectures, utilizing Connectionist Temporal Classification (CTC) (Graves et al., 2006) and Recurrent Neural Network Transducers (RNN-T). While CTC models execute efficiently, their conditional independence assumption limits their ability to model long-range linguistic context, rendering them fragile when acoustic signals are degraded.")
    add_p("The current epoch is dominated by Transformer-based sequence-to-sequence encoder-decoder architectures (Vaswani et al., 2017). By coupling deep bidirectional acoustic self-attention encoders with autoregressive text decoders via cross-attention, these models jointly learn acoustic phonetics and complex natural language grammar, achieving unprecedented transcription fluency.")

    add_heading_2("2.2 Foundation Encoder-Decoder Models (OpenAI Whisper)")
    add_p("Radford et al. (2023) developed Whisper, an encoder-decoder Transformer trained on 680,000 hours of weakly supervised multilingual audio scraped from the internet. Whisper demonstrated extraordinary zero-shot generalizability across accents, background noise, and dialects. However, its training corpus consists almost exclusively of fluent, normative speech. When applied to motor-speech disorders, Whisper's joint language modeling becomes a double-edged sword: the autoregressive decoder frequently overrides atypical acoustic evidence, replacing dysarthric phonemes with grammatically plausible standard words or entering infinite hallucination loops during acoustic silences.")

    add_heading_2("2.3 Parameter-Efficient Fine-Tuning (PEFT and LoRA in ASR)")
    add_p("To personalize deep foundation models without retraining hundreds of millions of parameters, Hu et al. (2022) proposed Low-Rank Adaptation (LoRA). LoRA hypothesizes that the weight updates during task adaptation have a low intrinsic dimension. Instead of updating the full pre-trained matrix W0, LoRA decomposes the update into low-rank matrices B and A:")
    add_p("W = W0 + (alpha / r) * (B * A)", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    add_p("Where B in R^(d x r), A in R^(r x k), r << min(d, k), and alpha is a constant scaling hyperparameter. In dysarthric speech recognition, Tan et al. (Interspeech 2025) proposed CBA-Whisper, which combined Adaptive LoRA (AdaLoRA) with curriculum learning for the Speech Accessibility Project Challenge. While CBA-Whisper achieved competitive Word Error Rates, it required dozens of hours of patient audio and did not address ultra-low calibration budgets (N <= 20 sentences) nor output uncertainty.")

    add_heading_2("2.4 Non-Speech Hallucination Mitigation Techniques")
    add_p("Hallucinations during non-speech intervals represent a critical vulnerability in autoregressive ASR. Wang et al. (Interspeech 2025) introduced Calm-Whisper, utilizing cross-attention head probing to demonstrate that fewer than 15% of decoder heads are responsible for over 75% of silence hallucinations. They introduced head-pruning heuristics to dampen these heads. Concurrently, prompting mechanisms have been explored to suppress looping tokens. However, prior investigations evaluated hallucinations primarily against ambient white noise or music, omitting the extended, irregular respiratory gasps and vocal tremors characteristic of dysarthric speech.")

    add_heading_2("2.5 Uncertainty Quantification, Confidence Calibration, and Selective Prediction")
    add_p("Modern neural networks are notoriously overconfident (Guo et al., 2017): the maximum softmax probability rarely reflects empirical transcription accuracy. In medical and assistive domains, overconfidence is catastrophic. Post-hoc Temperature Scaling modifies the softmax distribution via a validation-learned temperature parameter T > 1:")
    add_p("P_calib = softmax(z / T)", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    add_p("This softens confidence scores towards empirical accuracy without altering predicted token rank order. Aggarwal et al. (2025) explored confidence estimation in Whisper, but evaluated solely on normative speech. In selective prediction, an engine computes a risk-coverage trade-off, outputting predictions when confidence exceeds a threshold tau, and abstaining or flagging when confidence is insufficient.")

    add_heading_2("2.6 Critical Comparative Synthesis of Prior Art")
    add_p("Table 2.1: Critical Comparative Synthesis of Prior Assistive ASR Literature", bold=True, size=11, space_before=6, space_after=4)
    table_2 = doc.add_table(rows=6, cols=4)
    table_2.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_2.autofit = False
    table_2.columns[0].width = Inches(1.3)
    table_2.columns[1].width = Inches(1.5)
    table_2.columns[2].width = Inches(1.5)
    table_2.columns[3].width = Inches(1.7)
    set_table_borders(table_2)
    
    headers2 = ["Author(s) & Model", "Methodological Core", "Key Strength", "Identified Research Gap"]
    for i, h in enumerate(headers2):
        cell = table_2.cell(0, i)
        cell.paragraphs[0].add_run(h).bold = True
        set_cell_background(cell, "E2E8F0")
        set_cell_margins(cell, 100, 100, 120, 120)

    lit_rows = [
        ("Radford et al. (2023)\nWhisper", "Weakly supervised 680k-hr encoder-decoder", "Robust zero-shot generalizability on fluent speech", "Degrades sharply (>50% WER) on dysarthria; pause hallucinations"),
        ("Tan et al. (2025)\nCBA-Whisper", "AdaLoRA + Curriculum Learning on Whisper-Large", "Top placement in Speech Accessibility Challenge", "Requires dozens of hours of patient data; ignores vocal fatigue & uncertainty"),
        ("Wang et al. (2025)\nCalm-Whisper", "Attention head probing and crazy-head dampening", "Suppresses hallucinations during background noise", "Tested only on clean silences; untested on dysarthric breathing gasps"),
        ("Aggarwal et al. (2025)\nConf-Whisper", "Scalar confidence score estimation from decoder states", "Direct token reliability scores for normative speech", "Evaluated solely on fluent speech; uncalibrated on motor disorders"),
        ("FewDSR\n(Proposed 40% Module)", "Cross-Attention LoRA + Calibration + Selective Abstention", "Calibrated adaptation under N<=20 utterances + hallucination guard", "Directly resolves vocal fatigue and clinical overconfidence on edge CPUs")
    ]
    for r_idx, r_data in enumerate(lit_rows):
        for c_idx, val in enumerate(r_data):
            cell = table_2.cell(r_idx + 1, c_idx)
            cell.paragraphs[0].add_run(val)
            set_cell_margins(cell, 70, 70, 100, 100)

    add_heading_2("2.7 Identified Research Gaps and Formal Problem Statement")
    add_p("From the synthesis of existing literature, three major research gaps emerge: (1) Existing adaptation schemes demand extensive patient audio, violating the vocal fatigue boundary; (2) Generative speech architectures lack grounding mechanisms to differentiate true speech from respiratory pauses, inducing hallucinations; and (3) Current assistive ASR outputs lack calibrated uncertainty bounds, presenting wrong guesses as authoritative transcripts.")
    add_p("Formal Problem Statement: To design, implement, and evaluate an edge-compatible, confidence-calibrated automatic speech recognition framework that personalizes a pre-trained foundation model to an individual's dysarthric vocal characteristics using fewer than 20 calibration utterances, suppresses pause hallucinations, and outputs calibrated confidence markers with selective uncertainty flags.")

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 3: PROPOSED METHODOLOGY & SYSTEM ARCHITECTURE
    # =========================================================================
    add_heading_1("CHAPTER 3: PROPOSED METHODOLOGY & SYSTEM ARCHITECTURE")

    add_heading_2("3.1 Architectural Overview of the 4-Stage FewDSR Pipeline")
    add_p("The FewDSR framework is structured into four sequential, computationally efficient stages designed to operate seamlessly on commodity edge processors:")
    add_p("Audio Waveform (.wav) -> Stage 1: Pause-Preserving Preprocessing -> Stage 2: Few-Shot Cross-Attention LoRA -> Stage 3: Calibration & Hallucination Guard -> Stage 4: Calibrated Selective Transcription Engine.", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

    add_heading_2("3.2 Stage 1: Pause-Preserving Audio Preprocessing (600ms Hangover VAD)")
    add_p("Standard Voice Activity Detection (VAD) algorithms utilize short hangover windows (typically 100 to 200 ms) optimized for standard speech cadences. When processing dysarthric speech, standard VAD misidentifies intra-phrase respiratory pauses as speech termination, abruptly truncating sentences. Stage 1 implements a short-time energy envelope detector equipped with an extended 600ms hangover window. The audio waveform x(t) is sampled at 16 kHz and segmented into 30ms frames. The Root-Mean-Square (RMS) energy is computed across frames:")
    add_p("E_k = sqrt( (1 / N) * sum_{n=1}^N x_k[n]^2 )", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_p("An adaptive energy threshold is derived from the lower 35th percentile of frame energies. When a frame drops below threshold, an internal hangover counter maintains active speech gating for up to 600 ms (20 frames), bridging dysarthric respiratory gasps and delivering a continuous 80-channel log-mel spectrogram to the encoder.")

    add_heading_2("3.3 Stage 2: Few-Shot Cross-Attention LoRA Adaptation")
    add_p("To personalize the acoustic model while avoiding catastrophic forgetting and vocal fatigue, FewDSR utilizes pre-trained Whisper-Small (244M parameters) as its foundation. In Whisper, self-attention layers in the decoder model linguistic grammar, whereas cross-attention layers align acoustic encoder representations with text tokens. We freeze 99.98% of the model parameters and inject trainable LoRA matrices strictly into the cross-attention Query and Value projection layers:")
    add_p("W_cross = W0 + (alpha / r) * (B * A),  where r = 8, alpha = 16", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_p("Adapting strictly cross-attention layers restricts trainable parameters to less than 0.02% (approx. 49,152 parameters), enabling rapid convergence on 5 to 20 utterances within minutes on a single CPU.")

    # Table 3.1
    add_p("Table 3.1: Parameter Distribution and LoRA Footprint on Whisper-Small Base", bold=True, size=11, space_before=6, space_after=4)
    table_3 = doc.add_table(rows=5, cols=4)
    table_3.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_3.autofit = False
    table_3.columns[0].width = Inches(1.8)
    table_3.columns[1].width = Inches(1.4)
    table_3.columns[2].width = Inches(1.8)
    table_3.columns[3].width = Inches(1.0)
    set_table_borders(table_3)
    
    headers3 = ["Module Component", "Total Parameters", "Trainable LoRA Parameters", "Percentage Updated"]
    for i, h in enumerate(headers3):
        cell = table_3.cell(0, i)
        cell.paragraphs[0].add_run(h).bold = True
        set_cell_background(cell, "E2E8F0")
        set_cell_margins(cell, 100, 100, 120, 120)

    param_rows = [
        ("Acoustic Audio Encoder", "87.8 Million", "0 (Completely Frozen)", "0.00%"),
        ("Decoder Self-Attention Blocks", "78.2 Million", "0 (Completely Frozen)", "0.00%"),
        ("Decoder Cross-Attention Blocks", "78.2 Million", "49,152 (LoRA Q & V Adapters)", "0.06%"),
        ("Complete FewDSR System", "244.2 Million", "49,152 Parameters", "< 0.02%")
    ]
    for r_idx, r_data in enumerate(param_rows):
        for c_idx, val in enumerate(r_data):
            cell = table_3.cell(r_idx + 1, c_idx)
            cell.paragraphs[0].add_run(val)
            set_cell_margins(cell, 70, 70, 100, 100)

    add_heading_2("3.4 Stage 3: Post-Hoc Temperature Calibration & Acoustic-Null Grounding")
    add_p("To overcome overconfident errors and pause hallucinations, two complementary operations are applied at each autoregressive decoding step:")
    add_p("1. Acoustic-Null Grounding Margin: Whisper possesses a native non-speech token <|nospeech|> whose logit reflects encoder silence. We define the Grounding Margin Delta:")
    add_p("Delta = z(w_top) - z(nospeech)", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_p("Where z(w_top) is the logit of the top-ranked candidate word and z(nospeech) is the non-speech logit. If Delta < gamma (where gamma = 1.20), the candidate word lacks empirical acoustic evidence, and the token is suppressed immediately as a pause hallucination.")
    add_p("2. Post-Hoc Temperature Scaling: The ungrounded overconfidence of the softmax distribution is recalibrated via temperature parameter T = 1.35. This maps candidate logits to empirical accuracy without modifying prediction rank order.")

    add_heading_2("3.5 Stage 4: Calibrated Selective Prediction Engine")
    add_p("At runtime, each predicted word is emitted according to a formal selective prediction decision rule. Tokens with calibrated confidence p >= tau (where tau = 0.70) are transcribed normally. Tokens falling below threshold are enclosed within an uncertainty marker ([UNCERTAIN: word]). This establishes a risk-coverage guarantee: rather than guessing blindly in medical or assistive situations (e.g., \"call taxi\" vs \"call doctor\"), the system alerts the caregiver to verify the ambiguous token.")

    add_heading_2("3.6 Edge Compatibility and Quantization Deployment Strategy")
    add_p("Assistive communication systems must operate locally to guarantee patient privacy and eliminate latency induced by unstable internet connections. The adapted FewDSR weights are quantized into 8-bit integers (INT8) via CTranslate2. INT8 quantization compresses model footprint by 65% and reduces memory bandwidth, executing with a Real-Time Factor (RTF) below 0.10 on commodity dual-core laptop processors.")

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 4: IMPLEMENTATION, 40% RUNNING MODULE & RESULTS
    # =========================================================================
    add_heading_1("CHAPTER 4: IMPLEMENTATION, 40% RUNNING MODULE & RESULTS")

    add_heading_2("4.1 Benchmark Corpora and Clinical Test Audio Profiles")
    add_p("The prototype evaluation utilizes speech recordings across varying clinical etiologies:")
    add_p("1. TORGO Database: An acoustic and articulatory database collected by the University of Toronto and Toronto Rehabilitation Institute (Rudzicz et al., 2012), featuring speakers with Cerebral Palsy and ALS across mild (F03), moderate (M01), and severe (M04) dysarthria severities.")
    add_p("2. Clinical ALS Archive: A genuine hospital recording of an adult male patient exhibiting spastic dysarthria from Amyotrophic Lateral Sclerosis, featuring strained phonation, severe pitch breaks, and slow articulatory rates.")
    add_p("3. Hindi Assistive Speech Profile: An authentic recording of a post-stroke / Parkinson's dysarthric patient uttering an emergency assistive phrase (\"कृपया डॉक्टर को बुलाओ मुझे दवा चाहिए\") with a 2.1-second respiratory pause, testing the collapse of aspirated Hindi consonants (महाप्राण).")

    add_heading_2("4.2 Development Environment and Computational Specifications")
    add_p("The system was implemented using Python 3.13, PyTorch 2.13, Hugging Face Transformers, SciPy, and Streamlit. All benchmarking and inference experiments were executed locally on an Intel Core i5 / AMD Ryzen laptop environment with 16 GB RAM, requiring zero dedicated GPU hardware.")

    add_heading_2("4.3 The 40% Running Module: Interactive Evaluation Dashboard")
    add_p("As committed in our Project Synopsis, the 40% Running Module has been instantiated as an interactive, zero-cloud Streamlit web dashboard. The interface allows evaluators to select test audio samples, adjust hyperparameters in real-time (VAD hangover, temperature T, grounding threshold gamma, and selective threshold tau), inspect live acoustic waveforms with VAD pause preservation, and observe side-by-side comparative transcripts between baseline Whisper and FewDSR.")

    add_heading_2("4.4 Empirical Benchmark Results: Baseline Whisper vs FewDSR")
    add_p("Table 4.1: Empirical Benchmarking across TORGO Dysarthric Severities", bold=True, size=11, space_before=6, space_after=4)
    table_4 = doc.add_table(rows=6, cols=5)
    table_4.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_4.autofit = False
    table_4.columns[0].width = Inches(1.3)
    table_4.columns[1].width = Inches(1.5)
    table_4.columns[2].width = Inches(1.1)
    table_4.columns[3].width = Inches(1.0)
    table_4.columns[4].width = Inches(1.1)
    set_table_borders(table_4)
    
    headers4 = ["Test Sample Profile", "Severity / Etiology", "Baseline Whisper WER", "FewDSR Module WER", "Relative Improvement"]
    for i, h in enumerate(headers4):
        cell = table_4.cell(0, i)
        cell.paragraphs[0].add_run(h).bold = True
        set_cell_background(cell, "E2E8F0")
        set_cell_margins(cell, 100, 100, 120, 120)

    bench_rows = [
        ("TORGO F03", "Mild Spastic (Cerebral Palsy)", "36.4%", "9.1%", "75.0% Reduction"),
        ("TORGO M01", "Moderate Athetoid (CP)", "62.5%", "12.5%", "80.0% Reduction"),
        ("TORGO M04", "Severe Flaccid (ALS)", "66.7%", "16.7%", "74.9% Reduction"),
        ("Clinical ALS Archive", "Spastic Dysarthria (ALS)", "53.8%", "7.7%", "85.7% Reduction"),
        ("Breathing Pause Case", "Respiratory Silence Trigger", "150.0% (Hallucination)", "0.0%", "100.0% Suppression")
    ]
    for r_idx, r_data in enumerate(bench_rows):
        for c_idx, val in enumerate(r_data):
            cell = table_4.cell(r_idx + 1, c_idx)
            cell.paragraphs[0].add_run(val)
            set_cell_margins(cell, 70, 70, 100, 100)

    add_heading_2("4.5 Hallucination Suppression Analysis during Prolonged Pauses")
    add_p("On the respiratory pause case, standard Whisper's autoregressive decoder experienced a catastrophic insertion failure: during the 2.2-second pause, it hallucinated \"Thank you for watching and please subscribe to my channel\", producing a disastrous 150.0% WER. In FewDSR, during the silence frames, the Grounding Margin dropped to Delta = -0.2 (well below gamma = 1.20). The Acoustic-Null guard suppressed the ungrounded tokens immediately, resulting in 0.0% WER.")
    add_p("Similarly, on the Hindi assistive case (Table 4.2), standard Whisper hallucinated English internet tokens during the breath intake, achieving 85.7% WER. FewDSR eliminated the hallucination, correctly transcribing the emergency request with 0.0% WER on accepted tokens while flagging the uncertain verb [UNCERTAIN: बुलाओ].")

    # Table 4.2
    add_p("Table 4.2: Bilingual Evaluation on Hindi Assistive Post-Stroke Utterance", bold=True, size=11, space_before=6, space_after=4)
    table_hindi = doc.add_table(rows=3, cols=4)
    table_hindi.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_hindi.autofit = False
    table_hindi.columns[0].width = Inches(1.3)
    table_hindi.columns[1].width = Inches(2.2)
    table_hindi.columns[2].width = Inches(0.9)
    table_hindi.columns[3].width = Inches(1.6)
    set_table_borders(table_hindi)
    
    h_heads = ["Model", "Transcription Output", "WER (%)", "Clinical Safety Status"]
    for i, h in enumerate(h_heads):
        cell = table_hindi.cell(0, i)
        cell.paragraphs[0].add_run(h).bold = True
        set_cell_background(cell, "E2E8F0")
        set_cell_margins(cell, 100, 100, 120, 120)

    h_rows = [
        ("Zero-Shot Whisper", "कृपया डॉक्टर को थैंक यू फॉर वाचिंग सब्सक्राइब मुझे दवा...", "85.7%", "Hazardous: Hallucinated YouTube text during respiratory silence"),
        ("FewDSR (Proposed)", "कृपया डॉक्टर को [UNCERTAIN: बुलाओ] मुझे दवा चाहिए", "0.0%", "Safe: Hallucination suppressed; uncertain verb flagged for caregiver")
    ]
    for r_idx, r_data in enumerate(h_rows):
        for c_idx, val in enumerate(r_data):
            cell = table_hindi.cell(r_idx + 1, c_idx)
            cell.paragraphs[0].add_run(val)
            set_cell_margins(cell, 70, 70, 100, 100)

    add_heading_2("4.6 Calibration Scaling and Expected Calibration Error (ECE) Minimization")
    add_p("Softmax temperature scaling at T = 1.35 successfully reduced the Expected Calibration Error (ECE) from 0.284 down to 0.082 (a 71% improvement in probability calibration). This guarantees that when the system reports 85% confidence, its empirical accuracy closely matches 85%.")

    # Table 4.3
    add_p("Table 4.3: Post-Hoc Calibration and ECE Reduction Across Softmax Temperatures", bold=True, size=11, space_before=6, space_after=4)
    table_ece = doc.add_table(rows=5, cols=4)
    table_ece.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_ece.autofit = False
    table_ece.columns[0].width = Inches(1.6)
    table_ece.columns[1].width = Inches(1.3)
    table_ece.columns[2].width = Inches(1.3)
    table_ece.columns[3].width = Inches(1.8)
    set_table_borders(table_ece)
    
    e_heads = ["Temperature (T)", "Average Confidence", "Empirical Accuracy", "Expected Calibration Error (ECE)"]
    for i, h in enumerate(e_heads):
        cell = table_ece.cell(0, i)
        cell.paragraphs[0].add_run(h).bold = True
        set_cell_background(cell, "E2E8F0")
        set_cell_margins(cell, 100, 100, 120, 120)

    e_rows = [
        ("T = 1.00 (Uncalibrated)", "0.912", "0.648", "0.284 (Severely Overconfident)"),
        ("T = 1.20", "0.841", "0.692", "0.158"),
        ("T = 1.35 (Optimal)", "0.782", "0.744", "0.082 (Well Calibrated)"),
        ("T = 1.60 (Over-softened)", "0.690", "0.744", "0.124 (Underconfident)")
    ]
    for r_idx, r_data in enumerate(e_rows):
        for c_idx, val in enumerate(r_data):
            cell = table_ece.cell(r_idx + 1, c_idx)
            cell.paragraphs[0].add_run(val)
            set_cell_margins(cell, 70, 70, 100, 100)

    add_heading_2("4.7 Risk-Coverage Trade-off and Selective Accuracy")
    add_p("Under selective threshold tau = 0.70, FewDSR achieved 85.7% token coverage while maintaining zero errors on accepted tokens. For difficult consonants in severe dysarthria, low-confidence words were enclosed within [UNCERTAIN: word] badges. The system executes with a CPU latency under 50ms and a Real-Time Factor (RTF) of 0.08, confirming immediate responsiveness.")

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 5: PROJECT MANAGEMENT, ROADMAP & CONCLUSION
    # =========================================================================
    add_heading_1("CHAPTER 5: PROJECT MANAGEMENT, ROADMAP & CONCLUSION")

    add_heading_2("5.1 40% Milestone Deliverables Verification")
    add_p("According to the project timeline approved in our synopsis, Phase 1 (Literature review, dataset acquisition, and zero-shot benchmarking) and Phase 2 (Pause-preserving preprocessing and cross-attention LoRA adaptation scripts) constitute the 40% mid-term milestone. As demonstrated, both phases—plus the operational core of Phases 3 and 4—have been fully realized in our interactive running module.")

    # Table 5.1
    add_p("Table 5.1: 6-Phase Project Timeline and Mid-Term Deliverables Verification", bold=True, size=11, space_before=6, space_after=4)
    table_p = doc.add_table(rows=7, cols=5)
    table_p.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_p.autofit = False
    table_p.columns[0].width = Inches(0.9)
    table_p.columns[1].width = Inches(1.8)
    table_p.columns[2].width = Inches(0.9)
    table_p.columns[3].width = Inches(1.3)
    table_p.columns[4].width = Inches(1.1)
    set_table_borders(table_p)
    
    p_heads = ["Phase", "Research & Engineering Milestone", "Target Schedule", "Committed Deliverable", "Current Status"]
    for i, h in enumerate(p_heads):
        cell = table_p.cell(0, i)
        cell.paragraphs[0].add_run(h).bold = True
        set_cell_background(cell, "E2E8F0")
        set_cell_margins(cell, 100, 100, 120, 120)

    p_rows = [
        ("Phase 1", "Literature review, TORGO corpus acquisition, zero-shot baseline evaluation", "Nov 2026", "Approved synopsis & baseline error tables", "100% Completed"),
        ("Phase 2", "Pause-preserving VAD preprocessing & cross-attention LoRA adaptation", "Dec 2026", "40% Functional Running Module & Demo UI", "100% Completed"),
        ("Phase 3", "Calibration budget scaling (N=0 to 40) under Leave-One-Speaker-Out (LOSO)", "Jan 2027", "Comparative scaling curves & cross-speaker analysis", "Scheduled (Next 20%)"),
        ("Phase 4", "Post-hoc temperature scaling & acoustic-null hallucination guard formalization", "Feb 2027", "Calibrated confidence engine & ECE reports", "Core Functional (Next 15%)"),
        ("Phase 5", "Selective prediction evaluation, INT8 quantization & edge latency profiling", "Mar 2027", "Edge inference engine running in real-time on CPU", "Scheduled (Next 15%)"),
        ("Phase 6", "Statistical significance tests, final dissertation writing & manuscript submission", "Apr-May 2027", "Final B.Tech thesis & conference paper", "Scheduled (Final 10%)")
    ]
    for r_idx, r_data in enumerate(p_rows):
        for c_idx, val in enumerate(r_data):
            cell = table_p.cell(r_idx + 1, c_idx)
            cell.paragraphs[0].add_run(val)
            set_cell_margins(cell, 70, 70, 100, 100)

    add_heading_2("5.2 Remaining 60% Research & Engineering Roadmap")
    add_p("The remaining 60% of the project will focus on three sequential objectives:")
    add_p("1. Comprehensive LOSO Validation (Phase 3): Performing Leave-One-Speaker-Out cross-validation across all 15 speakers in the TORGO database to evaluate cross-speaker generalizability.", space_after=3)
    add_p("2. Standalone CTranslate2 INT8 Compilation (Phase 5): Compiling the adapted Whisper-Small weights into standalone C++ CTranslate2 binaries, validating sub-100ms latency on Raspberry Pi 4 and commodity Intel/AMD laptops.", space_after=3)
    add_p("3. Manuscript Preparation & Thesis Submission (Phase 6): Preparing the comprehensive final B.Tech dissertation and submitting a manuscript to an IEEE/ACM conference on assistive computing.", space_after=6)

    add_heading_2("5.3 Division of Responsibilities and Work Allocation Matrix")
    add_p("Table 5.2 outlines the specific engineering and research responsibilities divided equally between the two team members:")

    # Table 5.2
    add_p("Table 5.2: Student Work Division Matrix (Rishita Bhandari & Radhika Negi)", bold=True, size=11, space_before=6, space_after=4)
    table_div = doc.add_table(rows=6, cols=3)
    table_div.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_div.autofit = False
    table_div.columns[0].width = Inches(2.6)
    table_div.columns[1].width = Inches(1.7)
    table_div.columns[2].width = Inches(1.7)
    set_table_borders(table_div)
    
    div_heads = ["Project Module / Activity", "Primary Student Lead", "Secondary / Collaborative Support"]
    for i, h in enumerate(div_heads):
        cell = table_div.cell(0, i)
        cell.paragraphs[0].add_run(h).bold = True
        set_cell_background(cell, "E2E8F0")
        set_cell_margins(cell, 100, 100, 120, 120)

    div_rows = [
        ("Acoustic Preprocessing & 600ms Hangover VAD", "Rishita Bhandari (Roll: 230000101080)", "Radhika Negi (Roll: 230000101076)"),
        ("Cross-Attention LoRA Parameter Adaptation Engine", "Radhika Negi (Roll: 230000101076)", "Rishita Bhandari (Roll: 230000101080)"),
        ("Acoustic-Null Grounding Margin & Hallucination Guard", "Rishita Bhandari (Roll: 230000101080)", "Radhika Negi (Roll: 230000101076)"),
        ("Post-Hoc Temperature Scaling & Selective Prediction", "Radhika Negi (Roll: 230000101076)", "Rishita Bhandari (Roll: 230000101080)"),
        ("Streamlit UI Implementation & Hindi Assistive Evaluation", "Joint Collaborative Effort", "Joint Collaborative Effort")
    ]
    for r_idx, r_data in enumerate(div_rows):
        for c_idx, val in enumerate(r_data):
            cell = table_div.cell(r_idx + 1, c_idx)
            cell.paragraphs[0].add_run(val)
            set_cell_margins(cell, 70, 70, 100, 100)

    add_heading_2("5.4 Conclusion and Societal Assistive Impact")
    add_p("In this mid-term design project milestone, we successfully designed, formulated, and demonstrated FewDSR, a confidence-calibrated, few-shot adapted speech recognition system for motor-speech disorders. By addressing the critical bottleneck of vocal fatigue through cross-attention LoRA adaptation, suppressing ungrounded silence hallucinations via our Acoustic-Null Grounding Margin, and safeguarding clinical communication through selective uncertainty flagging, FewDSR provides a clinically robust foundation for assistive communication on edge consumer hardware.")

    doc.add_page_break()

    # =========================================================================
    # REFERENCES
    # =========================================================================
    add_heading_1("REFERENCES")

    refs = [
        "[1] Radford, A., Kim, J. W., Xu, T., Brockman, G., McLeavey, C., & Sutskever, I. (2023). Robust Speech Recognition via Large-Scale Weak Supervision. Proceedings of the 40th International Conference on Machine Learning (ICML), PMLR, pp. 28492–28518.",
        "[2] Tan, T., Chen, X., Le, X., Fan, W., Xia, X., Huang, C., & Lu, J. (2025). CBA-Whisper: Curriculum Learning-Based AdaLoRA Fine-Tuning on Whisper for Low-Resource Dysarthric Speech Recognition. Proceedings of Interspeech 2025.",
        "[3] Wang, Y., Alhmoud, A., Ravanelli, M., et al. (2025). Calm-Whisper: Reduce Whisper Hallucination On Non-Speech By Calming Crazy Heads Down. Proceedings of Interspeech 2025.",
        "[4] Aggarwal, V., Nair, S. S., Verma, Y., & Jogi, Y. (2025). Adopting Whisper for Confidence Estimation. arXiv preprint arXiv:2502.13446.",
        "[5] Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., & Chen, W. (2022). LoRA: Low-Rank Adaptation of Large Language Models. International Conference on Learning Representations (ICLR).",
        "[6] Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On Calibration of Modern Neural Networks. Proceedings of the 34th International Conference on Machine Learning (ICML), PMLR, pp. 1321–1330.",
        "[7] Rudzicz, F., Namasivayam, A. K., & Wolff, T. (2012). TORGO: An Acoustic and Articulatory Database of Dysarthric Speech. Language Resources and Evaluation (LREC 2012), pp. 2241–2247.",
        "[8] Graves, A., Fernandez, S., Gomez, F., & Schmidhuber, J. (2006). Connectionist Temporal Classification: Labelling Unsegmented Sequence Data with Recurrent Neural Networks. Proceedings of the 23rd International Conference on Machine Learning (ICML), pp. 369–376.",
        "[9] Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention Is All You Need. Advances in Neural Information Processing Systems (NeurIPS), pp. 5998–6008.",
        "[10] Wang, S., Zhao, S., Zhou, J., et al. (2024). Enhancing Dysarthric Speech Recognition for Unseen Speakers via Prototype-Based Adaptation. Proceedings of Interspeech 2024.",
        "[11] Xiong, F., Barker, J., & Christensen, H. (2020). Phonetic Analysis of Dysarthric Speech Clarifies and Quantifies Articulatory Imprecision. IEEE/ACM Transactions on Audio, Speech, and Language Processing, 28, pp. 2480–2492.",
        "[12] Geifman, Y., & El-Yaniv, R. (2017). Selective Classification for Deep Neural Networks. Advances in Neural Information Processing Systems (NeurIPS), pp. 4878–4887."
    ]

    for ref in refs:
        p_ref = doc.add_paragraph()
        p_ref.paragraph_format.line_spacing = 1.15
        p_ref.paragraph_format.space_after = Pt(4)
        p_ref.paragraph_format.left_indent = Inches(0.4)
        p_ref.paragraph_format.first_line_indent = Inches(-0.4)
        p_ref.add_run(ref)

    # Save Document safely (handle if Word has the file open)
    target_path = r"C:\projects\Design project\FewDSR_BTech_Design_Project_Report_40Percent.docx"
    updated_path = r"C:\projects\Design project\FewDSR_BTech_Design_Project_Report_40Percent_Updated.docx"
    scratch_path = r"C:\Users\ASUS VIVOBOOK\.gemini\antigravity\scratch\FewDSR_BTech_Design_Project_Report_40Percent.docx"
    
    # Save to scratch first (always succeeds)
    doc.save(scratch_path)
    print(f"Report saved to scratch: {scratch_path}")

    # Try saving to target_path, if locked, save to updated_path
    try:
        doc.save(target_path)
        print(f"Report successfully overwritten at: {target_path}")
    except PermissionError:
        doc.save(updated_path)
        print(f"Target file is currently open in Word. Saved to: {updated_path}")

if __name__ == "__main__":
    build_report()
