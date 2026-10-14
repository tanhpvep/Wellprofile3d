import streamlit as st
import pandas as pd
import well_profile as wp
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import io

# Cấu hình giao diện trang web hiển thị rộng rãi, chuyên nghiệp
st.set_page_config(layout="wide", page_title="Well Trajectory Plan vs Survey 3D")

st.title("📊 Ứng Dụng So Sánh Quỹ Đạo Giếng Khoan: Plan vs Survey")
st.write("Hỗ trợ tự động bóc tách 2 sheet riêng biệt (Plan & Survey) để hiển thị đồng thời trên cùng một biểu đồ.")

# Khung tải file Excel trực tiếp trên trình duyệt
uploaded_file = st.file_uploader("Kéo và thả file Excel (.xlsx / .xlsm) có chứa 2 sheet Plan và Survey vào đây", type=["xlsx", "xlsm"])

# Hàm phụ để tự động tìm hàng tiêu đề và dọn dẹp dữ liệu cho từng sheet lẻ
def clean_well_sheet(uploaded_file, sheet_name):
    try:
        raw_df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=None)
        header_row = None
        for idx, row in raw_df.iterrows():
            row_items = [str(x).strip().lower() if pd.notna(x) else "" for x in row.values]
            row_text = " ".join(row_items)
            
            has_md = ('md' in row_text) or ('measured' in row_text) or ('depth' in row_text)
            has_inc = ('inc' in row_text) or ('incl' in row_text) or ('angle' in row_text)
            has_azi = ('azi' in row_text) or ('azim' in row_text) or ('azm' in row_text) or ('azimuth' in row_text)
            
            if has_md and has_inc and has_azi and len(row_text) > 10:
                header_row = idx
                break
        if header_row is None:
            header_row = 0
            
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=header_row)
        df.columns = df.columns.str.replace(r'\s+', ' ', regex=True).str.strip().str.lower()
        
        df_clean = pd.DataFrame()
        md_col = [c for c in df.columns if 'md' in c or 'measured' in c or 'depth' in c]
        inc_col = [c for c in df.columns if 'inc' in c or 'incl' in c]
        inc_col = [c for c in inc_col if 'comment' not in c and 'rate' not in c and 'vsec' not in c]
        azi_col = [c for c in df.columns if 'azi' in c or 'azim' in c or 'azm' in c or 'azimuth' in c]
        azi_col = [c for c in azi_col if 'comment' not in c and 'rate' not in c]
        
        if md_col and inc_col and azi_col:
            df_clean['md'] = pd.to_numeric(df[md_col[0]], errors='coerce')
            df_clean['inc'] = pd.to_numeric(df[inc_col[0]], errors='coerce')
            df_clean['azi'] = pd.to_numeric(df[azi_col[0]], errors='coerce')
            df_clean = df_clean.dropna()
            return df_clean.to_dict(orient='records')
        return None
    except:
        return None

if uploaded_file is not None:
    try:
        xl = pd.ExcelFile(uploaded_file)
        sheet_names = xl.sheet_names
        
        plan_sheet = None
        survey_sheet = None
        
        for sheet in sheet_names:
            low_sheet = sheet.lower()
            if 'plan' in low_sheet:
                plan_sheet = sheet
            elif 'survey' in low_sheet or 'actual' in low_sheet or 'data' in low_sheet or 'sheet1' in low_sheet:
                survey_sheet = sheet
                
        if not plan_sheet and len(sheet_names) > 0: plan_sheet = sheet_names[0]
        if not survey_sheet and len(sheet_names) > 1: survey_sheet = sheet_names[1]
        elif not survey_sheet and len(sheet_names) == 1: survey_sheet = sheet_names[0]

        wells_to_plot = []
        geo_data_dict = {}
        
        # 2. XỬ LÝ CHÈN DỮ LIỆU SHEET PLAN
        if plan_sheet and plan_sheet != survey_sheet:
            plan_dict = clean_well_sheet(uploaded_file, plan_sheet)
            if plan_dict:
                well_plan = wp.load(plan_dict, inner_pts=5, set_info={'wellType': 'offshore', 'units': 'metric'}, set_start={'north': 0, 'east': 0, 'depth': 0})
                wells_to_plot.append((well_plan, "Well Plan (Thiết kế)", "dash", "black")) 
                df_plan = well_plan.df()
                df_plan['vs_calculated'] = np.sqrt(df_plan['east']**2 + df_plan['north']**2)
                geo_data_dict["Well Plan (Thiết kế)"] = df_plan
                st.sidebar.success(f"✓ Đã nạp thành công dữ liệu Thiết kế: {plan_sheet}")

        # 3. XỬ LÝ CHÈN DỮ LIỆU SHEET SURVEY
        if survey_sheet:
            survey_dict = clean_well_sheet(uploaded_file, survey_sheet)
            if survey_dict:
                well_survey = wp.load(survey_dict, inner_pts=5, set_info={'wellType': 'offshore', 'units': 'metric'}, set_start={'north': 0, 'east': 0, 'depth': 0})
                wells_to_plot.append((well_survey, "Well Survey (Thực tế)", "solid", "red")) 
                df_survey = well_survey.df()
                df_survey['vs_calculated'] = np.sqrt(df_survey['east']**2 + df_survey['north']**2)
                geo_data_dict["Well Survey (Thực tế)"] = df_survey
                st.sidebar.success(f"✓ Đã nạp thành công dữ liệu Thực tế: {survey_sheet}")

        if not wells_to_plot:
            st.error("Không thể trích xuất cấu trúc dữ liệu hợp lệ từ các sheet!")
            st.stop()

        # 4. KHỞI TẠO BỐ CỤC ĐỒ THỊ SUBPLOTS 3 MÀN HÌNH CHUNG 1 TAB
        fig = make_subplots(
            rows=2, cols=2, column_widths=[0.55, 0.45], row_heights=[0.5, 0.5],
            specs=[[[{"type": "scene", "rowspan": 2}, {"type": "xy"}], [None, {"type": "xy"}]]],
            subplot_titles=("3D Wellbore Trajectory Profile (Colored by DLS)", "Horizontal View (Plan View - Top Down)", "Vertical View (Cross Section - Profile)")
        )

        # A. DỰNG MÔ HÌNH HÌNH HỌC 3D (Bên trái)
        for well_obj, name, line_style, color_name in wells_to_plot:
            fig_base = well_obj.plot(style={'color': 'dls', 'size': 1})
            for trace in fig_base.data:
                trace.showlegend = False 
                
                if color_name == "black":
                    trace.mode = 'lines'
                    trace.line.color = 'rgb(120, 120, 120)' 
                    trace.line.width = 3
                    trace.line.dash = "dash"
                    trace.marker.showscale = False
                else:
                    trace.mode = 'lines+markers'
                    trace.line.width = 5
                    trace.marker.showscale = True
                    trace.marker.colorscale = 'Jet' 
                    trace.marker.size = 3
                    trace.marker.colorbar = dict(
                        title="DLS (deg/30m)",
                        thickness=15,
                        x=1.15, 
                        y=0.5
                    )
                    
                fig.add_trace(trace, row=1, col=1)

        # B. DỰNG MẶT BẰNG & MẶT ĐỨNG CÓ ĐỔ MÀU DLS THEO CHẤM TRÒN (Bên phải)
        for name, geo_df in geo_data_dict.items():
            is_plan = "Plan" in name
            line_style = "dash" if is_plan else "solid"
            line_width = 3 if is_plan else 5 
            
            if is_plan:
                fig.add_trace(
                    go.Scatter(
                        x=geo_df['east'], y=geo_df['north'], mode='lines',
                        line=dict(color='rgb(120, 120, 120)', width=line_width, dash=line_style), 
                        name=name, showlegend=True 
                    ), row=1, col=2
                )
                fig.add_trace(
                    go.Scatter(
                        x=geo_df['vs_calculated'], y=geo_df['tvd'], mode='lines',
                        line=dict(color='rgb(120, 120, 120)', width=line_width, dash=line_style), 
                        name=name, showlegend=False 
                    ), row=2, col=2
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=geo_df['east'], y=geo_df['north'], mode='lines+markers',
                        marker=dict(size=4, color=geo_df['dls'], colorscale='Jet', showscale=False),
                        line=dict(color='rgb(214, 39, 40)', width=line_width), 
                        name=name, showlegend=True 
                    ), row=1, col=2
                )
                fig.add_trace(
                    go.Scatter(
                        x=geo_df['vs_calculated'], y=geo_df['tvd'], mode='lines+markers',
                        marker=dict(size=4, color=geo_df['dls'], colorscale='Jet', showscale=False),
                        line=dict(color='rgb(214, 39, 40)', width=line_width), 
                        name=name, showlegend=False 
                    ), row=2, col=2
                )

        # 5. CẤU HÌNH HỆ TRỤC TỌA ĐỘ VÀ ĐỒNG BỘ TỶ LỆ THỰC HÌNH HỌC
        fig.update_xaxes(title_text="Easting / East (m)", row=1, col=2)
        fig.update_yaxes(title_text="Northing / North (m)", scaleanchor="x", scaleratio=1, row=1, col=2)
        fig.update_xaxes(title_text="Vertical Section / Displacement (m)", row=2, col=2)
        fig.update_yaxes(title_text="True Vertical Depth - TVD (m)", autorange='reversed', row=2, col=2)
        
        fig.update_layout(
            height=850,
            showlegend=True, 
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=1.02), 
            scene=dict(
                xaxis_title="East (m)", yaxis_title="North (m)", zaxis_title="TVD (m)",
                zaxis=dict(autorange='reversed'), aspectmode='data',
                camera=dict(eye=dict(x=1.8, y=1.8, z=0.5))
            )
        )

        st.plotly_chart(fig, use_container_width=True)
        
        # 6. TẠO BỘ NHỚ ĐỆM ĐỂ TẢI FILE HTML
        buffer = io.StringIO()
        fig.write_html(buffer, include_plotlyjs='cdn')
        html_bytes = buffer.getvalue().encode()
        
        st.download_button(
            label="💾 Tải file đồ thị HTML so sánh Plan vs Survey về máy của bạn",
            data=html_bytes,
            file_name=f"Plan_vs_Survey_multi_view.html",
            mime="text/html"
        )
        
