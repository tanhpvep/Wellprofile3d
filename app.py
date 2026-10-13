import streamlit as st
import pandas as pd
import well_profile as wp
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import io

# Cấu hình giao diện trang web hiển thị rộng rãi, chuyên nghiệp
st.set_page_config(layout="wide", page_title="Well Trajectory Visualizer 3D")

st.title("📊 Ứng Dụng Trực Quan Quỹ Đạo Giếng Khoan Đa Góc Nhìn")
st.write("Dành cho Kỹ sư khoan. Hỗ trợ tự động dọn dẹp cấu trúc file báo cáo Baker Hughes, Schlumberger...")

# 1. KHUNG KÉO THẢ FILE EXCEL TRÊN TRÌNH DUYỆT TRỰC TIẾP
uploaded_file = st.file_uploader("Kéo và thả file Excel (.xlsx / .xlsm) của bạn vào đây", type=["xlsx", "xlsm"])

if uploaded_file is not None:
    try:
        # Đọc danh sách sheet để tự động nhận diện sheet phù hợp
        xl = pd.ExcelFile(uploaded_file)
        sheet_names = xl.sheet_names
        selected_sheet = sheet_names[0] # Mặc định lấy sheet đầu tiên nếu không khớp từ khóa
        
        priority_keywords = ['plan', 'survey', 'trajectory', 'quỹ đạo', 'data', 'bhareport', 'wgr', 'planned wgr']
        found_sheet = False
        for kw in priority_keywords:
            for sheet in sheet_names:
                if kw in sheet.lower():
                    selected_sheet = sheet
                    found_sheet = True
                    break
            if found_sheet:
                break
        
        # 2. THUẬT TOÁN DÒ TÌM DÒNG TIÊU ĐỀ SIÊU NỚI LỎNG (Đã sửa lỗi lệch chỉ mục do ô trống)
        raw_df = pd.read_excel(uploaded_file, sheet_name=selected_sheet, header=None)
        header_row = None
        
        for idx, row in raw_df.iterrows():
            # Giữ nguyên độ dài hàng, biến NaN thành chuỗi rỗng để chốt chính xác dòng 23
            row_items = [str(x).strip().lower() if pd.notna(x) else "" for x in row.values]
            row_text = " ".join(row_items)
            
            has_md = ('md' in row_text) or ('measured' in row_text) or ('depth' in row_text)
            has_inc = ('inc' in row_text) or ('incl' in row_text) or ('angle' in row_text)
            has_azi = ('azi' in row_text) or ('azim' in row_text) or ('azimuth' in row_text)
            
            if has_md and has_inc and has_azi and len(row_text) > 15:
                header_row = idx
                break

        if header_row is None:
            header_row = 0
            
        # 3. TRÍCH XUẤT CỘT CHỨA CHUỖI CON THÔNG MINH
        df = pd.read_excel(uploaded_file, sheet_name=selected_sheet, header=header_row)
        df.columns = df.columns.str.replace(r'\s+', ' ', regex=True).str.strip().str.lower()
        
        df_clean = pd.DataFrame()
        md_col = [c for c in df.columns if 'md' in c or 'measured' in c or 'depth' in c]
        inc_col = [c for c in df.columns if 'inc' in c or 'incl' in c]
        inc_col = [c for c in inc_col if 'comment' not in c and 'rate' not in c and 'vsec' not in c]
        azi_col = [c for c in df.columns if 'azi' in c or 'azim' in c or 'azimuth' in c]
        azi_col = [c for c in azi_col if 'comment' not in c and 'rate' not in c]
        
        # Đồng bộ logic đã kiểm tra OK 100% dưới máy tính của bạn
        if md_col and inc_col and azi_col:
            df_clean['md'] = pd.to_numeric(df[md_col[0]], errors='coerce')
            df_clean['inc'] = pd.to_numeric(df[inc_col[0]], errors='coerce')
            df_clean['azi'] = pd.to_numeric(df[azi_col[0]], errors='coerce')
        else:
            st.error(f"Không tự động tìm thấy các cột hình học! Quét được: MD={md_col}, INC={inc_col}, AZI={azi_col}")
            st.stop()
            
        df_clean = df_clean.dropna()
        data_dict = df_clean.to_dict(orient='records')
        
        # 4. TÍNH TOÁN WELL PROFILE BẰNG PYTHAGORAS
        well = wp.load(data_dict, inner_pts=5, set_info={'dlsResolution': 30, 'wellType': 'offshore', 'units': 'metric'}, set_start={'north': 0, 'east': 0, 'depth': 0})
        geo_data = well.df()
        geo_data['vs_calculated'] = np.sqrt(geo_data['east']**2 + geo_data['north']**2)
        
        # 5. KHỞI TẠO BỐ CỤC ĐỒ THỊ SUBPLOTS 3 MÀN HÌNH CHUNG 1 TAB
        fig = make_subplots(
            rows=2, cols=2, column_widths=[0.50, 0.50], row_heights=[0.5, 0.5],
            specs=[[{"type": "scene", "rowspan": 2}, {"type": "xy"}], [None, {"type": "xy"}]],
            subplot_titles=("3D Wellbore Profile (Colored by DLS)", "Horizontal View (Plan View)", "Vertical View (Profile)")
        )
        
        fig_3d_base = well.plot(style={'color': 'dls', 'size': 3})
        for trace in fig_3d_base.data:
            fig.add_trace(trace, row=1, col=1)
            
        fig.add_trace(go.Scatter(x=geo_data['east'], y=geo_data['north'], mode='lines+markers', marker=dict(size=3, color=geo_data['dls'], colorscale='Jet'), line=dict(color='gray', width=2)), row=1, col=2)
        fig.add_trace(go.Scatter(x=geo_data['vs_calculated'], y=geo_data['tvd'], mode='lines+markers', marker=dict(size=3, color=geo_data['dls'], colorscale='Jet'), line=dict(color='gray', width=2)), row=2, col=2)
        
        fig.update_xaxes(title_text="Easting / East (m)", row=1, col=2)
        fig.update_yaxes(title_text="Northing / North (m)", scaleanchor="x", scaleratio=1, row=1, col=2)
        fig.update_xaxes(title_text="Vertical Section / Displacement (m)", row=2, col=2)
        fig.update_yaxes(title_text="True Vertical Depth - TVD (m)", autorange='reversed', row=2, col=2)
        fig.update_layout(height=850, showlegend=False, scene=dict(xaxis_title="East (m)", yaxis_title="North (m)", zaxis_title="TVD (m)", zaxis=dict(autorange='reversed'), aspectmode='data', camera=dict(eye=dict(x=1.8, y=1.8, z=0.5))))
        
        # 6. HIỂN THỊ ĐỒ THỊ TRỰC TIẾP TRÊN TRÌNH DUYỆT WEB KHÁCH HÀNG
        st.plotly_chart(fig, use_container_width=True)
        
        # 7. TẠO BỘ NHỚ ĐỆM ĐỂ KHÁCH TỰ BẤM TẢI FILE HTML VỀ MÁY CỦA HỌ
        buffer = io.StringIO()
        fig.write_html(buffer, include_plotlyjs='cdn')
        html_bytes = buffer.getvalue().encode()
        
        st.download_button(
            label="💾 Tải file đồ thị HTML tương tác 3D về máy của bạn",
            data=html_bytes,
            file_name=f"Trajectory_multi_view.html",
            mime="text/html"
        )
        st.success("🎉 Đã xử lý và hiển thị đồ thị quỹ đạo thành công!")
        
    except Exception as e:
        st.error(f"Lỗi xử lý file hệ thống: {e}")
