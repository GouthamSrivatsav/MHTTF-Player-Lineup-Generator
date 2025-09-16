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

# Simplified approach - no longer using pyppeteer

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

def wrap_long_text(text, max_len=15):
    """Wrap text using <br> tags for Plotly tables"""
    if len(text) <= max_len:
        return text
    # Find a good break point (space, /, etc.) or force break
    words = text.split()
    if len(words) > 1:
        mid = len(words) // 2
        return "<br>".join([" ".join(words[:mid]), " ".join(words[mid:])])
    else:
        # Force break long single words
        return "<br>".join([text[i:i+max_len] for i in range(0, len(text), max_len)])

# HTML approach removed - using Plotly + pyppeteer instead

def create_lineup_image(selected_lineup, team_name, mobile_optimized=False):
    """Create lineup image - simplified Plotly approach"""
    
    print("DEBUG - create_lineup_image called")
    print(f"DEBUG - PLOTLY_AVAILABLE: {PLOTLY_AVAILABLE}")
    print(f"DEBUG - MATPLOTLIB_AVAILABLE: {MATPLOTLIB_AVAILABLE}")
    
    # Try Plotly first (simplified approach)
    if PLOTLY_AVAILABLE:
        try:
            print("DEBUG - Attempting Plotly approach...")
            result = create_plotly_table_image(selected_lineup, team_name, mobile_optimized)
            print("DEBUG - Plotly succeeded!")
            return result
        except Exception as plotly_error:
            print(f"DEBUG - Plotly failed: {plotly_error}")
            import traceback
            traceback.print_exc()
    
    # Fallback to matplotlib
    if MATPLOTLIB_AVAILABLE:
        try:
            print("DEBUG - Falling back to matplotlib...")
            result = create_matplotlib_table(selected_lineup, team_name, mobile_optimized)
            print("DEBUG - Matplotlib succeeded!")
            return result
        except Exception as mpl_error:
            print(f"DEBUG - Matplotlib failed: {mpl_error}")
    
    # Final fallback to PIL
    print("DEBUG - Using PIL fallback...")
    return create_simple_pil_fallback(selected_lineup, team_name, mobile_optimized)

def create_plotly_table_image(selected_lineup, team_name, mobile_optimized=False):
    """Create Plotly table with proper <br> tag support"""
    
    print("DEBUG - create_plotly_table_image called!")
    print(f"DEBUG - selected_lineup type: {type(selected_lineup)}")
    print(f"DEBUG - team_name: {team_name}")
    print(f"DEBUG - mobile_optimized: {mobile_optimized}")
    
    try:
        # Process real data now that we know Plotly works
        rounds_order = ["S1", "S2", "S3", "D1", "D2", "D3", "D4", "D5"]
        lineup_data = []
        
        print("DEBUG - Processing REAL data")
        print("DEBUG - Input selected_lineup:", selected_lineup)
        
        for round_name in rounds_order:
            if round_name in selected_lineup:
                selection = selected_lineup[round_name]
                print(f"DEBUG - {round_name}: raw selection = {selection} (type: {type(selection)})")
                # Use the existing format_player_names function with Plotly flag
                player_text = format_player_names(selection, for_plotly=True)
                print(f"DEBUG - {round_name}: formatted = '{player_text}'")
            else:
                player_text = "Not selected"
                print(f"DEBUG - {round_name}: Not selected")
            lineup_data.append([round_name, player_text])
        
        print("DEBUG - Full lineup_data:", lineup_data)
        
        # Extract data into explicit lists
        final_rounds = [row[0] for row in lineup_data]
        final_players = [row[1] for row in lineup_data]
        
        print("DEBUG - REAL final_rounds:", final_rounds)
        print("DEBUG - REAL final_players:", final_players)
        
        # Additional debug for cloud issues
        print("DEBUG - Verifying data alignment:")
        for i, (round_name, player_name) in enumerate(zip(final_rounds, final_players)):
            print(f"DEBUG - Row {i}: '{round_name}' -> '{player_name}'")
        
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
        
        # CLOUD-ROBUST APPROACH: Build table data more explicitly
        # Create table data as individual cell values to avoid cloud serialization issues
        print("DEBUG - Building cloud-robust table data...")
        
        # Ensure we have exactly 8 rows in correct order
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
                    print(f"DEBUG - Found {round_name}: '{found_player}'")
                    break
            table_players.append(found_player)
        
        print("DEBUG - CLOUD table_rounds:", table_rounds)
        print("DEBUG - CLOUD table_players:", table_players)
        
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
        
        # Update layout with explicit width control and better sizing
        fig.update_layout(
            title=dict(
                text=f"<b>Team: {team_name}</b>",
                x=0.5,
                y=0.95,
                xanchor='center',
                yanchor='top',
                font=dict(size=title_font_size, color='black', family="Arial Black")
            ),
            autosize=False,
            width=1000 if not mobile_optimized else 800,  # Wider overall table
            height=height,
            margin=dict(l=50, r=50, t=title_margin, b=50),
            paper_bgcolor='#FFF8DC',  # Cornsilk background
            plot_bgcolor='#FFF8DC',   # Cornsilk background
            font_family="Arial"
        )
        
        # Update traces with taller rows and explicit column values
        fig.update_traces(
            cells=dict(
                values=[table_rounds, table_players],  # Use cloud-robust data
                height=50 if not mobile_optimized else 60,  # Taller rows for wrapped text
                fill_color='#FFA07A',  # Light Salmon
                align=['center', 'left'],
                font=dict(color='black', size=cell_font_size, family="Arial")
            ),
            columnwidth=[150, 650] if not mobile_optimized else [120, 520]  # Explicit column widths
        )
        
        # Try plotly export with cloud-friendly settings
        export_width = 1000 if not mobile_optimized else 800  # Match layout width
        try:
            # Try with different scale settings for cloud compatibility
            img_bytes = pio.to_image(fig, format='png', width=export_width, height=height, scale=1)
            return img_bytes
        except Exception as plotly_error:
            try:
                # Fallback: try without scale parameter
                img_bytes = pio.to_image(fig, format='png', width=export_width, height=height)
                return img_bytes
            except Exception as plotly_error2:
                # If plotly fails completely, use matplotlib fallback
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
                if len(combined) > 20:  # Same threshold as Plotly
                    player_text = f"{selection[0]} /\n{selection[1]}"  # Use \n for matplotlib
                else:
                    player_text = combined
            else:
                player_text = format_player_names(selection)
        else:
            player_text = "Not selected"
        lineup_data.append([round_name, player_text])
        # Track the longest player text
        max_player_text_length = max(max_player_text_length, len(player_text.replace('\n', '')))  # Don't count newlines in length
    
    # Simplified: Always use wide player column to prevent cropping
    round_col_width = 0.1   # Very narrow round column
    player_col_width = 0.9  # Very wide player column
    
    # Simplified: Always use very wide tables to prevent cropping
    if mobile_optimized:
        # Mobile: VERY wide to handle any text length
        figsize = (12, 8)   # Extra wide for mobile
        title_fontsize = 18
        table_fontsize = 14
        dpi = 120
    else:
        # Desktop: Professional width
        figsize = (10, 10)
        title_fontsize = 24
        table_fontsize = 16
        dpi = 150
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.axis('tight')
    ax.axis('off')
    
    # Set background color
    fig.patch.set_facecolor('#FFF8DC')  # Cornsilk
    
    # Create table with dynamic column widths
    table = ax.table(
        cellText=lineup_data,
        colLabels=['Round', 'Player(s)'],
        cellLoc='left',
        loc='center',
        colWidths=[round_col_width, player_col_width]
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
    
    # Style data cells and handle newlines by replacing cell content
    for i in range(1, len(lineup_data) + 1):
        for j in range(2):
            table[(i, j)].set_facecolor('#FFA07A')  # Light Salmon
            table[(i, j)].set_text_props(color='black')
            
            # Check if this cell has a newline and handle it specially
            cell_text = str(lineup_data[i-1][j])
            if '\n' in cell_text and j == 1:  # Only for player column
                # Clear the original cell text
                table[(i, j)].get_text().set_text('')
                table[(i, j)].set_height(0.15)  # Much taller for multi-line
                
                # Calculate the position of this cell to overlay custom text
                # This is a hack but should work better than relying on table cell text handling
                lines = cell_text.split('\n')
                for line_idx, line in enumerate(lines):
                    # Position text manually within the cell area
                    y_offset = 0.02 * line_idx  # Small offset for each line
                    ax.text(0.3, 0.85 - (i-1) * 0.1 - y_offset, line,
                           transform=ax.transAxes,
                           fontsize=table_fontsize,
                           va='center', ha='left',
                           color='black')
            else:
                table[(i, j)].set_height(0.08)  # Normal height
            
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
    # Download button with on-demand image generation
    # @st.cache_data  # TEMPORARILY DISABLED FOR DEBUGGING
    def generate_lineup_image(selected_lineup_dict, team_name_str):
        print("DEBUG - generate_lineup_image called!")
        print(f"DEBUG - selected_lineup_dict: {selected_lineup_dict}")
        print(f"DEBUG - team_name_str: {team_name_str}")
        result = create_lineup_image(selected_lineup_dict, team_name_str, mobile_optimized=False)
        print(f"DEBUG - create_lineup_image returned {len(result) if result else 0} bytes")
        return result
    
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
        st.error(f"Error creating image: {str(e)}")
    
    st.divider()
    
    # Reset button
    if st.button("🔄 Reset All Selections", type="secondary"):
        st.session_state.selected_lineup = {}
        st.rerun()
