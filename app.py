import streamlit as st
import pandas as pd
import itertools
from PIL import Image, ImageDraw, ImageFont
import io
import base64
try:
    import imgkit
    IMGKIT_AVAILABLE = True
except ImportError:
    IMGKIT_AVAILABLE = False
    
try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

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

def create_lineup_html_table(selected_lineup, team_name, mobile_optimized=False):
    """Create HTML table for lineup that can be converted to image"""
    
    # Define rounds in proper order
    rounds_order = ["S1", "S2", "S3", "D1", "D2", "D3", "D4", "D5"]
    
    # Create DataFrame for the lineup
    lineup_data = []
    for round_name in rounds_order:
        if round_name in selected_lineup:
            selection = selected_lineup[round_name]
            player_text = format_player_names(selection)
        else:
            player_text = "Not selected"
        lineup_data.append({"Round": round_name, "Player(s)": player_text})
    
    df = pd.DataFrame(lineup_data)
    
    # Mobile or desktop styling
    if mobile_optimized:
        # Mobile-optimized CSS
        table_style = """
        <style>
        body {
            margin: 0;
            padding: 20px;
            background-color: #FFF8DC;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background-color: #FFF8DC;
        }
        h1 {
            text-align: center;
            font-size: 48px;
            font-weight: bold;
            color: #000;
            margin: 30px 0;
            line-height: 1.2;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background-color: #FFA07A;
            border: 3px solid #006064;
            font-size: 36px;
            font-weight: bold;
        }
        th {
            background-color: #FFA07A;
            color: #000;
            padding: 25px 20px;
            text-align: left;
            border: 2px solid #006064;
            font-size: 38px;
            font-weight: bold;
        }
        td {
            padding: 25px 20px;
            border: 2px solid #006064;
            color: #000;
            font-weight: bold;
            line-height: 1.3;
            word-wrap: break-word;
        }
        .round-col {
            width: 25%;
            text-align: center;
            font-size: 38px;
        }
        .player-col {
            width: 75%;
            font-size: 34px;
        }
        </style>
        """
    else:
        # Desktop/Print-optimized CSS
        table_style = """
        <style>
        body {
            margin: 0;
            padding: 40px;
            background-color: #FFF8DC;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background-color: #FFF8DC;
        }
        h1 {
            text-align: center;
            font-size: 48px;
            font-weight: bold;
            color: #000;
            margin: 40px 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background-color: #FFA07A;
            border: 3px solid #006064;
            font-size: 24px;
            font-weight: bold;
        }
        th {
            background-color: #FFA07A;
            color: #000;
            padding: 20px;
            text-align: left;
            border: 2px solid #006064;
            font-size: 28px;
            font-weight: bold;
        }
        td {
            padding: 20px;
            border: 2px solid #006064;
            color: #000;
            font-weight: bold;
        }
        .round-col {
            width: 20%;
            text-align: center;
            font-size: 26px;
        }
        .player-col {
            width: 80%;
            font-size: 24px;
        }
        </style>
        """
    
    # Generate HTML with CSS
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        {table_style}
    </head>
    <body>
        <div class="container">
            <h1>Team: {team_name}</h1>
            <table>
                <thead>
                    <tr>
                        <th class="round-col">Round</th>
                        <th class="player-col">Player(s)</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for _, row in df.iterrows():
        html_content += f"""
                    <tr>
                        <td class="round-col">{row['Round']}</td>
                        <td class="player-col">{row['Player(s)']}</td>
                    </tr>
        """
    
    html_content += """
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    
    return html_content

def create_lineup_image(selected_lineup, team_name, mobile_optimized=False):
    """Create lineup image using HTML-to-image conversion for better text rendering"""
    
    # Try HTML-to-image approach first
    try:
        html_content = create_lineup_html_table(selected_lineup, team_name, mobile_optimized)
        
        # Try imgkit first (requires wkhtmltopdf)
        if IMGKIT_AVAILABLE:
            try:
                options = {
                    'format': 'png',
                    'encoding': "UTF-8",
                    'enable-local-file-access': None,
                    'width': 600 if mobile_optimized else 1000,
                    'height': 1200 if mobile_optimized else 1400,
                    'quality': 100,
                }
                img_data = imgkit.from_string(html_content, False, options=options)
                return img_data
            except Exception as e:
                st.warning(f"imgkit failed: {e}")
        
        # Try weasyprint as fallback
        if WEASYPRINT_AVAILABLE:
            try:
                html_doc = weasyprint.HTML(string=html_content)
                png_bytes = html_doc.write_png()
                return png_bytes
            except Exception as e:
                st.warning(f"weasyprint failed: {e}")
        
        # If both fail, fall back to PIL silently
        pass
        
    except Exception as e:
        st.error(f"HTML rendering failed: {e}")
    
    # Fallback to PIL method - but much simpler
    if mobile_optimized:
        width, height = 600, 1200
        title_size, text_size = 60, 48
        row_height = 100
    else:
        width, height = 800, 1400
        title_size, text_size = 48, 32
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
    
    # Simple title
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
