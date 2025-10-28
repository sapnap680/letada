import os
import logging

import json
import time
import traceback
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# ---- 小さなユーティリティ（self を使わない形で実装） ----
def _truncate_text(text, max_chars=15):
    logger = logging.getLogger(__name__)
    try:
        if text is None:
            return ""
        s = str(text)
        s = s.replace("\n", " ").replace("\r", " ")
        return s if len(s) <= max_chars else s[:max_chars-2] + ".."
    except Exception:
        return ""

def _write_job_meta(job_meta_path, **kwargs):
    logger = logging.getLogger(__name__)
    try:
        meta = {}
        if os.path.exists(job_meta_path):
            with open(job_meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        meta.update(kwargs)
        with open(job_meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # 可能な限り例外を握りつぶしつつ標準出力には出す
        print("Failed to write job meta:", e)

def pdf_worker_main(reports, output_path, job_meta_path, max_rows_per_page=100):
    logger = logging.getLogger(__name__)
    """
    別プロセスで実行する PDF 生成ロジック。
    - reports: シリアライズ可能な dict (大学名 -> report)
    - output_path: 最終出力（ここでは zip か pdf）
    - job_meta_path: 進捗を保存する json ファイル
    """
    try:
        _write_job_meta(job_meta_path, status="running", progress=0.0, message="generating", started_at=datetime.utcnow().isoformat()+"Z")

        # 総ステップ数（大学 × ページ数）
        total_steps = 0
        per_univ_pages = {}
        for univ_name, report in reports.items():
            results = report.get("results", []) if report else []
            pages = (len(results) + max_rows_per_page - 1) // max_rows_per_page
            per_univ_pages[univ_name] = max(1, pages)
            total_steps += per_univ_pages[univ_name]
        if total_steps == 0:
            total_steps = 1

        # ここでは「大学ごとに個別 PDF を作り、最後に zip にする」戦略をとる
        # まず出力ディレクトリを用意
        out_dir = os.path.splitext(output_path)[0] + "_parts"
        os.makedirs(out_dir, exist_ok=True)

        step_done = 0
        styles = getSampleStyleSheet()
        compact_style = ParagraphStyle('Compact', parent=styles['Normal'], fontSize=6, leading=6, fontName='Helvetica')
        title_style = ParagraphStyle('TitleCompact', parent=styles['Title'], fontSize=8, leading=9, fontName='Helvetica')

        # 大学ごとに PDF を作成して保存
        for univ_name, report in reports.items():
            safe_name = "".join(c for c in univ_name if c.isalnum() or c in " _-")[:60] or "univ"
            part_path = os.path.join(out_dir, f"{safe_name}.pdf")
            doc = SimpleDocTemplate(part_path, pagesize=A4, leftMargin=8*mm, rightMargin=8*mm, topMargin=10*mm, bottomMargin=10*mm)
            elements = []
            elements.append(Paragraph(f"🏀 {univ_name} 選手データ", title_style))
            elements.append(Spacer(1, 1))

            results = (report or {}).get("results", [])
            total_pages = per_univ_pages.get(univ_name, 1)

            for page_num in range(total_pages):
                start = page_num * max_rows_per_page
                end = min(start + max_rows_per_page, len(results))
                page_results = results[start:end]

                data = [["No", "選手名", "学年", "身長", "体重", "ポジション", "出身校", "JBA"]]
                for idx, r in enumerate(page_results, start=start+1):
                    d = r.get("original_data", {})
                    status = r.get("status", "unknown")
                    symbol = "✓" if status == "match" else ("△" if status == "partial_match" else ("×" if status == "not_found" else "-"))
                    row = [
                        _truncate_text(d.get("背番号", ""), 3),
                        _truncate_text(d.get("選手名", d.get("氏名", "")), 12),
                        _truncate_text(d.get("学年", ""), 3),
                        _truncate_text(d.get("身長", ""), 6),
                        _truncate_text(d.get("体重", ""), 6),
                        _truncate_text(d.get("ポジション", ""), 8),
                        _truncate_text(d.get("出身校", ""), 12),
                        symbol
                    ]
                    data.append(row)

                from reportlab.platypus import Table, TableStyle
                col_widths = [10*mm, 40*mm, 10*mm, 12*mm, 12*mm, 20*mm, 30*mm, 8*mm]
                row_heights = [10] + [7] * (len(data)-1)
                table = Table(data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), colors.HexColor('#666666')),
                    ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
                    ("FONTSIZE", (0,1), (-1,-1), 6),
                    ("GRID", (0,0), (-1,-1), 0.2, colors.grey)
                ]))
                elements.append(table)
                if page_num < total_pages - 1:
                    elements.append(PageBreak())

                # 進捗更新（ページ単位）
                step_done += 1
                _write_job_meta(job_meta_path, progress=step_done/total_steps, message=f"processing {univ_name} page {page_num+1}/{total_pages}")

            # PDF を書き出す（大学ごとに doc.build）
            doc.build(elements)
            # 大学分の PDF を作ったら即座にメタに保存（ファイルパスを記録）
            _write_job_meta(job_meta_path, last_generated_part=part_path, message=f"generated {safe_name}")

        # すべて出来たら zip にまとめる
        import zipfile
        zip_path = output_path if output_path.lower().endswith(".zip") else output_path + ".zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fname in sorted(os.listdir(out_dir)):
                zf.write(os.path.join(out_dir, fname), arcname=fname)

        _write_job_meta(job_meta_path, status="done", progress=1.0, message="completed", output_path=zip_path, completed_at=datetime.utcnow().isoformat()+"Z")
    except Exception as e:
        tb = traceback.format_exc()
        print("PDF worker crashed:", e)
        _write_job_meta(job_meta_path, status="error", progress=0.0, message=str(e), error=tb)

