"""
Download Image Function Module
Handles all image generation and download functionality for the MHTTF Lineup Generator
"""

import streamlit as st
import pandas as pd

# Import required libraries with fallbacks
try:
    import plotly.graph_objects as go
    import plotly.io as pio
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def format_player_names(option, for_plotly=False):
    """Format player names with / for doubles pairs, plain text for singles"""
    if isinstance(option, tuple):
        if len(option) >= 2:
            combined = " / ".join(option)
            if for_plotly and len(combined) > 20:  # Wrap long names for Plotly
                # Break at the / for doubles
                return f"{option[0]} /<br>{option[1]}"
            return combined
        elif len(option) == 1:
            return option[0]
        else:
            return "Invalid selection"
    return option


def create_lineup_image(selected_lineup, team_name, mobile_optimized=False):
    """Create lineup image - simplified Plotly approach"""
    
    # Try Plotly first (simplified approach)
    if PLOTLY_AVAILABLE:
        try:
            return create_plotly_table_image(selected_lineup, team_name, mobile_optimized)
        except Exception as plotly_error:
            pass
    
    # Fallback to matplotlib
    if MATPLOTLIB_AVAILABLE:
        try:
            return create_matplotlib_table(selected_lineup, team_name, mobile_optimized)
        except Exception as mpl_error:
            pass
    
    # Final fallback to PIL
    return create_simple_pil_fallback(selected_lineup, team_name, mobile_optimized)


def create_plotly_table_image(selected_lineup, team_name, mobile_optimized=False):
    """Create Plotly table with proper <br> tag support"""
    
    try:
        # Process real data
        rounds_order = ["S1", "S2", "S3", "D1", "D2", "D3", "D4", "D5"]
        lineup_data = []
        
        for round_name in rounds_order:
            if round_name in selected_lineup:
                selection = selected_lineup[round_name]
                player_text = format_player_names(selection, for_plotly=True)
            else:
                player_text = "Not selected"
            lineup_data.append([round_name, player_text])
        
        # Extract data into explicit lists
        final_rounds = [row[0] for row in lineup_data]
        final_players = [row[1] for row in lineup_data]
        
        # Mobile vs Desktop settings
        if mobile_optimized:
            width, height = 600, 1000
            title_font_size = 28
            header_font_size = 22
            cell_font_size = 20
            cell_height = 60
            title_margin = 80
        else:
            width, height = 900, 1200
            title_font_size = 36
            header_font_size = 28
            cell_font_size = 24
            cell_height = 70
            title_margin = 100
        
        # Cloud-robust approach: Build table data more explicitly
        table_rounds = []
        table_players = []
        
        expected_rounds = ["S1", "S2", "S3", "D1", "D2", "D3", "D4", "D5"]
        for round_name in expected_rounds:
            table_rounds.append(round_name)
            # Find the player for this specific round
            found_player = "Not selected"
            for i, (data_round, data_player) in enumerate(zip(final_rounds, final_players)):
                if data_round == round_name:
                    found_player = data_player
                    break
            table_players.append(found_player)
        
        # Create Plotly table with taller cells for wrapped text
        wrapped_cell_height = cell_height * 1.5 if any('<br>' in str(text) for text in table_players) else cell_height
        
        fig = go.Figure(data=[go.Table(
            columnwidth=[100, 400],
            header=dict(
                values=['<b>Round</b>', '<b>Player(s)</b>'],
                fill_color='#FFA07A',  # Light Salmon
                align='center',
                font=dict(color='black', size=header_font_size, family="Arial Black"),
                height=cell_height
            ),
            cells=dict(
                values=[table_rounds, table_players],  # Use cloud-robust explicit mapping
                fill_color='#FFA07A',  # Light Salmon
                align=['center', 'left'],
                font=dict(color='black', size=cell_font_size, family="Arial"),
                height=wrapped_cell_height
            )
        )])
        
        # Update layout - no title, we'll add it separately
        fig.update_layout(
            autosize=False,
            width=1000 if not mobile_optimized else 800,
            height=height,
            margin=dict(l=50, r=50, t=80, b=50),  # Reduced top margin since no title
            paper_bgcolor='#FFF8DC',  # Cornsilk background
            plot_bgcolor='#FFF8DC',   # Cornsilk background
            font_family="Arial",
            showlegend=False
        )
        
        # Add title as annotation for better control
        fig.add_annotation(
            text=f"<b>Team: {team_name}</b>",
            x=0.5,
            y=1.08,  # Position above the table
            xref="paper",
            yref="paper",
            xanchor="center",
            yanchor="bottom",
            font=dict(size=title_font_size, color='black', family="Arial Black"),
            showarrow=False,
            bgcolor='rgba(255,248,220,0)',  # Transparent background
        )
        
        # Update traces
        fig.update_traces(
            cells=dict(
                values=[table_rounds, table_players],
                height=50 if not mobile_optimized else 60,
                fill_color='#FFA07A',  # Light Salmon
                align=['center', 'left'],
                font=dict(color='black', size=cell_font_size, family="Arial")
            ),
            columnwidth=[150, 650] if not mobile_optimized else [120, 520]
        )
        
        # Export image
        export_width = 1000 if not mobile_optimized else 800
        try:
            img_bytes = pio.to_image(fig, format='png', width=export_width, height=height, scale=1)
            return img_bytes
        except Exception as plotly_error:
            try:
                img_bytes = pio.to_image(fig, format='png', width=export_width, height=height)
                return img_bytes
            except Exception as plotly_error2:
                raise Exception(f"Plotly export failed: {plotly_error2}")
        
    except Exception as e:
        # Try matplotlib fallback if available
        if MATPLOTLIB_AVAILABLE:
            try:
                return create_matplotlib_table(selected_lineup, team_name, mobile_optimized)
            except Exception as mpl_error:
                pass  # Matplotlib failed, continue to PIL fallback
        
        # Final fallback to enhanced PIL
        return create_simple_pil_fallback(selected_lineup, team_name, mobile_optimized)


def create_matplotlib_table(selected_lineup, team_name, mobile_optimized=False):
    """Create table using matplotlib - works reliably on cloud platforms"""
    
    # Create DataFrame for the lineup
    rounds_order = ["S1", "S2", "S3", "D1", "D2", "D3", "D4", "D5"]
    lineup_data = []
    max_player_text_length = 0
    
    for round_name in rounds_order:
        if round_name in selected_lineup:
            selection = selected_lineup[round_name]
            # Use matplotlib-compatible line breaks for long text
            if isinstance(selection, tuple) and len(selection) >= 2:
                combined = " / ".join(selection)
                if len(combined) > 20:  # Break long doubles for readability
                    player_text = f"{selection[0]} /\n{selection[1]}"
                else:
                    player_text = combined
            else:
                player_text = format_player_names(selection)
            max_player_text_length = max(max_player_text_length, len(player_text))
        else:
            player_text = "Not selected"
        lineup_data.append([round_name, player_text])
    
    df = pd.DataFrame(lineup_data, columns=["Round", "Player(s)"])
    
    # Calculate figure size based on content
    if mobile_optimized:
        fig_width = 8
        fig_height = 12
        title_size = 18
        header_size = 14
        cell_size = 12
    else:
        fig_width = 10
        fig_height = 14
        title_size = 24
        header_size = 18
        cell_size = 16
    
    # Create matplotlib figure
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis('tight')
    ax.axis('off')
    
    # Create table
    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc='left',
        loc='center',
        colWidths=[0.15, 0.85]
    )
    
    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(cell_size)
    table.scale(1, 3)  # Make rows taller
    
    # Style header
    for i, col in enumerate(df.columns):
        table[(0, i)].set_facecolor('#FFA07A')
        table[(0, i)].set_text_props(weight='bold', size=header_size)
        table[(0, i)].set_height(0.1)
    
    # Style data cells
    for i in range(1, len(df) + 1):
        for j in range(len(df.columns)):
            table[(i, j)].set_facecolor('#FFA07A')
            table[(i, j)].set_height(0.12)
            if j == 0:  # Round column - center align
                table[(i, j)].set_text_props(ha='center', weight='bold')
            else:  # Player column - left align
                table[(i, j)].set_text_props(ha='left', va='center')
    
    # Add title
    plt.title(f'Team: {team_name}', fontsize=title_size, fontweight='bold', pad=20)
    
    # Set background
    fig.patch.set_facecolor('#FFF8DC')  # Cornsilk background
    
    # Save to bytes
    import io
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight', 
                facecolor='#FFF8DC', edgecolor='none')
    plt.close()
    img_buffer.seek(0)
    return img_buffer.getvalue()


def create_simple_pil_fallback(selected_lineup, team_name, mobile_optimized=False):
    """Simple PIL fallback when other methods fail"""
    
    if not PIL_AVAILABLE:
        # Return a simple text-based fallback
        return b"Image generation failed - PIL not available"
    
    # Create a simple image with PIL
    if mobile_optimized:
        width, height = 800, 1000
        title_size = 32
        text_size = 24
    else:
        width, height = 1000, 1200
        title_size = 40
        text_size = 28
    
    # Create image
    img = Image.new('RGB', (width, height), '#FFF8DC')  # Cornsilk background
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("arial.ttf", title_size)
        text_font = ImageFont.truetype("arial.ttf", text_size)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
    
    # Draw title
    title_text = f"Team: {team_name}"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(((width - title_width) // 2, 50), title_text, fill='black', font=title_font)
    
    # Draw table
    y_start = 150
    row_height = 80
    rounds_order = ["S1", "S2", "S3", "D1", "D2", "D3", "D4", "D5"]
    
    for i, round_name in enumerate(rounds_order):
        y_pos = y_start + i * row_height
        
        # Draw round
        draw.text((50, y_pos), round_name, fill='black', font=text_font)
        
        # Draw player
        if round_name in selected_lineup:
            selection = selected_lineup[round_name]
            player_text = format_player_names(selection)
        else:
            player_text = "Not selected"
        
        draw.text((200, y_pos), player_text, fill='black', font=text_font)
    
    # Save to bytes
    import io
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer.getvalue()


@st.cache_data
def generate_lineup_image(selected_lineup_dict, team_name_str):
    """Generate lineup image with caching"""
    return create_lineup_image(selected_lineup_dict, team_name_str, mobile_optimized=False)


def render_download_section(team_name):
    """Render the download button section"""
    try:
        # Only generate image when there are selections
        if st.session_state.selected_lineup:
            image_data = generate_lineup_image(
                dict(st.session_state.selected_lineup), 
                team_name
            )
            st.download_button(
                label="📸 Download Lineup Image",
                data=image_data,
                file_name=f"MHTTF_Lineup_{team_name}.png",
                mime="image/png",
                type="primary",
                help="Download high-quality lineup image"
            )
        else:
            st.info("🎾 Select players to enable download")
    except Exception as e:
        st.error(f"Error generating image: {str(e)}")
        st.info("Please try selecting players again or refresh the page.")
