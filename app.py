import streamlit as st
import pandas as pd
import itertools
from PIL import Image, ImageDraw, ImageFont
import io
import base64
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

# Configure Streamlit page layout for full screen width
st.set_page_config(page_title="MHTTF Village League Tennis Lineup Generator", layout="wide")

# Password protection
def check_password():
    """Returns True if the user has entered the correct password."""
    
    def password_entered():
        """Checks whether the password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password
        else:
            st.session_state["password_correct"] = False

    # Return True if password is validated
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password
    st.title("🔐 MHTTF Village League Tennis Lineup Generator")
    st.markdown("### Please enter the password to access the application")
    
    st.text_input(
        "Password", 
        type="password", 
        on_change=password_entered, 
        key="password",
        placeholder="Enter password..."
    )
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ Incorrect password. Please try again.")
    
    return False

# Check password before showing the app
if not check_password():
    st.stop()

# Add custom CSS for sticky sidebar
st.markdown("""
<style>
    /* Target the specific column containing the current lineup */
    [data-testid="column"]:nth-child(2) {
        position: sticky;
        top: 2rem;
        height: fit-content;
        max-height: calc(100vh - 4rem);
        overflow-y: auto;
        background-color: #f8f9fa;
        border-radius: 0.5rem;
        border: 1px solid #e9ecef;
        padding: 1rem;
        margin-top: 0;
    }
    
    /* Custom scrollbar */
    [data-testid="column"]:nth-child(2)::-webkit-scrollbar {
        width: 6px;
    }
    
    [data-testid="column"]:nth-child(2)::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 3px;
    }
    
    [data-testid="column"]:nth-child(2)::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 3px;
    }
    
    [data-testid="column"]:nth-child(2)::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8;
    }
</style>
""", unsafe_allow_html=True)

# ---- Eligibility rules ----
def eligible_s1(r): return r in {4.0, 4.5}
def eligible_s2(r): return r in {3.0, 3.5}
def eligible_s3(r): return r == 3.0
def eligible_d1(r1, r2): return r1 + r2 in {8.0, 8.5}
def eligible_d2_d3(r1, r2): return r1 + r2 in {7.0, 7.5}
def eligible_d4_d5(r1, r2): return r1 + r2 in {6.0, 6.5}

def generate_candidates(players):
    singles = players[["player_name", "player_rating"]].to_dict("records")
    s1 = [(p["player_name"],) for p in singles if eligible_s1(p["player_rating"])]
    s2 = [(p["player_name"],) for p in singles if eligible_s2(p["player_rating"])]
    s3 = [(p["player_name"],) for p in singles if eligible_s3(p["player_rating"])]

    d1, d2, d3, d4, d5 = [], [], [], [], []
    for p1, p2 in itertools.combinations(singles, 2):
        pair = (p1["player_name"], p2["player_name"])
        total = p1["player_rating"] + p2["player_rating"]
        if eligible_d1(p1["player_rating"], p2["player_rating"]): d1.append(pair)
        if eligible_d2_d3(p1["player_rating"], p2["player_rating"]):
            d2.append(pair); d3.append(pair)
        if eligible_d4_d5(p1["player_rating"], p2["player_rating"]):
            d4.append(pair); d5.append(pair)

    return {"S1": s1, "S2": s2, "S3": s3, "D1": d1, "D2": d2, "D3": d3, "D4": d4, "D5": d5}

def valid_lineups(candidates, max_results=200):
    rounds = ["S1", "S2", "S3", "D1", "D2", "D3", "D4", "D5"]
    results = []

    def backtrack(idx, used, current):
        if len(results) >= max_results:
            return
        if idx == len(rounds):
            results.append(current.copy())
            return
        r = rounds[idx]
        for option in candidates[r]:
            if not set(option) & used:
                current[r] = option
                backtrack(idx + 1, used | set(option), current)
                del current[r]

    backtrack(0, set(), {})
    return results

# ---- Streamlit UI ----
st.title("🎾 MHTTF Village League Tennis Lineup Generator")

try:
    # Load players_info.xlsx from current folder
    df = pd.read_excel("players_info.xlsx")
    # Filter out nan values and convert to list
    teams = [team for team in df["team"].unique() if pd.notna(team)]
    
    # Set default team to Wicklund if it exists in the list
    default_index = 0
    if "Wicklund" in teams:
        default_index = teams.index("Wicklund")
    
    team_name = st.selectbox("Select team", teams, index=default_index)
except FileNotFoundError:
    st.error("📁 players_info.xlsx file not found in the current folder. Please make sure the file exists.")
    st.stop()
except Exception as e:
    st.error(f"❌ Error loading players_info.xlsx: {str(e)}")
    st.stop()

players = df[df["team"] == team_name].reset_index(drop=True)
candidates = generate_candidates(players)

# Initialize session state for selections
if 'selected_lineup' not in st.session_state:
    st.session_state.selected_lineup = {}

# Function to get currently used players
def get_used_players():
    used = set()
    for selection in st.session_state.selected_lineup.values():
        if isinstance(selection, tuple):
            used.update(selection)
        elif isinstance(selection, str):
            used.add(selection)
    return used

# Function to check if a player/pair is available
def is_available(option):
    used_players = get_used_players()
    if isinstance(option, tuple):
        return not (set(option) & used_players)
    return option not in used_players

# Function to format player names (singles or doubles)
def format_player_names(option):
    """Format player names with / for doubles pairs, plain text for singles"""
    if isinstance(option, tuple):
        return " / ".join(option)
    return option


def create_lineup_image(selected_lineup, team_name, mobile_optimized=False):
    """Create lineup image using Plotly table for better text rendering"""
    
    if not PLOTLY_AVAILABLE:
        # Fallback to PIL if plotly not available
        return create_simple_pil_fallback(selected_lineup, team_name, mobile_optimized)
    
    try:
        # Create DataFrame for the lineup
        rounds_order = ["S1", "S2", "S3", "D1", "D2", "D3", "D4", "D5"]
        lineup_data = []
        
        for round_name in rounds_order:
            if round_name in selected_lineup:
                selection = selected_lineup[round_name]
                player_text = format_player_names(selection)
            else:
                player_text = "Not selected"
            lineup_data.append([round_name, player_text])
        
        df = pd.DataFrame(lineup_data, columns=["Round", "Player(s)"])
        
        # Mobile vs Desktop settings
        if mobile_optimized:
            # Mobile-optimized settings
            width, height = 600, 1000
            title_font_size = 28
            header_font_size = 22
            cell_font_size = 20
            cell_height = 60
            title_margin = 80
        else:
            # Desktop-optimized settings
            width, height = 900, 1200
            title_font_size = 36
            header_font_size = 28
            cell_font_size = 24
            cell_height = 70
            title_margin = 100
        
        # Create Plotly table
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
                values=[df['Round'], df['Player(s)']],
                fill_color='#FFA07A',  # Light Salmon
                align=['center', 'left'],
                font=dict(color='black', size=cell_font_size, family="Arial"),
                height=cell_height
            )
        )])
        
        # Update layout with title and styling
        fig.update_layout(
            title=dict(
                text=f"<b>Team: {team_name}</b>",
                x=0.5,
                y=0.95,
                xanchor='center',
                yanchor='top',
                font=dict(size=title_font_size, color='black', family="Arial Black")
            ),
            width=width,
            height=height,
            margin=dict(l=50, r=50, t=title_margin, b=50),
            paper_bgcolor='#FFF8DC',  # Cornsilk background
            plot_bgcolor='#FFF8DC',   # Cornsilk background
            font_family="Arial"
        )
        
        # Try plotly export with simplified approach
        try:
            # Try without specifying engine (let plotly decide)
            img_bytes = pio.to_image(fig, format='png', width=width, height=height, scale=2)
            return img_bytes
        except Exception as plotly_error:
            # If plotly fails, use matplotlib fallback silently
            raise Exception(f"Plotly export failed: {plotly_error}")
        
    except Exception as e:
        # Try matplotlib fallback if available
        if MATPLOTLIB_AVAILABLE:
            try:
                return create_matplotlib_table(selected_lineup, team_name, mobile_optimized)
            except Exception as mpl_error:
                st.warning(f"Matplotlib also failed: {mpl_error}")
        
        # Final fallback to enhanced PIL
        return create_simple_pil_fallback(selected_lineup, team_name, mobile_optimized)

def create_matplotlib_table(selected_lineup, team_name, mobile_optimized=False):
    """Create table using matplotlib - works reliably on cloud platforms"""
    
    # Create DataFrame for the lineup
    rounds_order = ["S1", "S2", "S3", "D1", "D2", "D3", "D4", "D5"]
    lineup_data = []
    
    for round_name in rounds_order:
        if round_name in selected_lineup:
            selection = selected_lineup[round_name]
            player_text = format_player_names(selection)
        else:
            player_text = "Not selected"
        lineup_data.append([round_name, player_text])
    
    # Mobile vs Desktop settings
    if mobile_optimized:
        figsize = (6, 8)
        title_fontsize = 20
        table_fontsize = 14
        dpi = 150
    else:
        figsize = (8, 10)
        title_fontsize = 24
        table_fontsize = 16
        dpi = 200
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.axis('tight')
    ax.axis('off')
    
    # Set background color
    fig.patch.set_facecolor('#FFF8DC')  # Cornsilk
    
    # Create table
    table = ax.table(
        cellText=lineup_data,
        colLabels=['Round', 'Player(s)'],
        cellLoc='left',
        loc='center',
        colWidths=[0.2, 0.8]
    )
    
    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(table_fontsize)
    table.scale(1, 2.5)
    
    # Style header
    for i in range(2):  # 2 columns
        table[(0, i)].set_facecolor('#FFA07A')  # Light Salmon
        table[(0, i)].set_text_props(weight='bold', color='black')
        table[(0, i)].set_height(0.08)
    
    # Style data cells
    for i in range(1, len(lineup_data) + 1):
        for j in range(2):
            table[(i, j)].set_facecolor('#FFA07A')  # Light Salmon
            table[(i, j)].set_text_props(color='black')
            table[(i, j)].set_height(0.08)
            if j == 0:  # Round column - center align
                table[(i, j)].set_text_props(ha='center')
    
    # Add title
    plt.title(f'Team: {team_name}', fontsize=title_fontsize, weight='bold', 
              color='black', pad=20)
    
    # Save to bytes
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', 
                facecolor='#FFF8DC', dpi=dpi)
    plt.close()
    img_buffer.seek(0)
    
    return img_buffer.getvalue()

def create_simple_pil_fallback(selected_lineup, team_name, mobile_optimized=False):
    """Simple PIL fallback if Plotly fails"""
    
    if mobile_optimized:
        width, height = 600, 1200
        title_size, text_size = 40, 32
        row_height = 100
    else:
        width, height = 800, 1400
        title_size, text_size = 32, 24
        row_height = 80
    
    # Create simple image
    img = Image.new('RGB', (width, height), (255, 248, 220))
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", title_size)
        text_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", text_size)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
    
    # Title
    draw.text((50, 50), f"Team: {team_name}", fill=(0, 0, 0), font=title_font)
    
    # Simple table
    rounds_order = ["S1", "S2", "S3", "D1", "D2", "D3", "D4", "D5"]
    y_pos = 150
    
    for round_name in rounds_order:
        if round_name in selected_lineup:
            selection = selected_lineup[round_name]
            player_text = format_player_names(selection)
        else:
            player_text = "Not selected"
        
        draw.text((50, y_pos), f"{round_name}: {player_text}", fill=(0, 0, 0), font=text_font)
        y_pos += row_height
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG', quality=100)
    img_buffer.seek(0)
    return img_buffer.getvalue()

st.header("Select Players for Each Round")

# Create columns for better layout
col1, col2 = st.columns([2, 1])

with col1:
    # Display each round with selectable options
    rounds_info = {
        "S1": "S1",
        "S2": "S2", 
        "S3": "S3",
        "D1": "D1",
        "D2": "D2",
        "D3": "D3",
        "D4": "D4",
        "D5": "D5"
    }
    
    for round_name, round_desc in rounds_info.items():
        # Add player info to expander title if selected
        title_suffix = ""
        if round_name in st.session_state.selected_lineup:
            selected = st.session_state.selected_lineup[round_name]
            selected_text = format_player_names(selected)
            # Use non-breaking spaces for visible separation
            title_suffix = f"\u00A0\u00A0\u00A0\u00A0✅ {selected_text}"
        
        # Create collapsible expander for each round (closed by default)
        # Show selection info in title if selected
        with st.expander(f"{round_name}{title_suffix}", expanded=False):
            # Show clear button at the top if there's a selection
            if round_name in st.session_state.selected_lineup:
                selected = st.session_state.selected_lineup[round_name]
                selected_text = format_player_names(selected)
                
                # Create columns for current selection and clear button at the top
                top_col1, top_col2 = st.columns([3, 1])
                with top_col1:
                    st.success(f"Current: {selected_text}")
                with top_col2:
                    if st.button("❌ Clear", key=f"top_clear_{round_name}", help="Clear selection"):
                        del st.session_state.selected_lineup[round_name]
                        st.rerun()
                
                st.divider()  # Separator between current selection and options
            
            # Get available options for this round
            available_options = [opt for opt in candidates[round_name] if is_available(opt)]
            
            # Create buttons for each option (only if there are available options)
            if available_options:
                cols = st.columns(min(4, len(available_options)))
                for i, option in enumerate(available_options):
                    col_idx = i % 4
                    with cols[col_idx]:
                        option_text = format_player_names(option)
                        is_selected = st.session_state.selected_lineup.get(round_name) == option
                        
                        button_help = "Click to deselect" if is_selected else "Click to select"
                        if st.button(
                            option_text, 
                            key=f"{round_name}_{i}",
                            type="primary" if is_selected else "secondary",
                            help=button_help
                        ):
                            if is_selected:
                                # Deselect if already selected
                                if round_name in st.session_state.selected_lineup:
                                    del st.session_state.selected_lineup[round_name]
                            else:
                                # Select this option
                                st.session_state.selected_lineup[round_name] = option
                            st.rerun()
            
            # Show status message if no selection
            if round_name not in st.session_state.selected_lineup:
                st.info("No selection made")
        

with col2:
    # Main download button to trigger format selection
    if st.button("📸 Download Lineup Image", type="primary"):
        st.session_state.show_download_options = True
    
    # Show download format options after main button is clicked
    if st.session_state.get("show_download_options", False):
        st.write("**Choose format:**")
        
        # Mobile-friendly download button
        try:
            mobile_image_data = create_lineup_image(st.session_state.selected_lineup, team_name, mobile_optimized=True)
            st.download_button(
                label="📱 Mobile Friendly",
                data=mobile_image_data,
                file_name=f"MHTTF_Lineup_{team_name}_Mobile.png",
                mime="image/png",
                help="Optimized for mobile viewing with large fonts"
            )
        except Exception as e:
            st.error(f"Error creating mobile image: {str(e)}")
        
        # Desktop-friendly download button
        try:
            desktop_image_data = create_lineup_image(st.session_state.selected_lineup, team_name, mobile_optimized=False)
            st.download_button(
                label="🖥️ Desktop Friendly",
                data=desktop_image_data,
                file_name=f"MHTTF_Lineup_{team_name}_Desktop.png",
                mime="image/png",
                help="High-resolution image perfect for desktop viewing and printing"
            )
        except Exception as e:
            st.error(f"Error creating desktop image: {str(e)}")
    
    st.divider()
    
    # Reset button
    if st.button("🔄 Reset All Selections", type="secondary"):
        st.session_state.selected_lineup = {}
        st.rerun()
