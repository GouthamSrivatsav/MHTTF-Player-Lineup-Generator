import streamlit as st
import pandas as pd
import itertools
from PIL import Image, ImageDraw, ImageFont
import io

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

def create_lineup_image(selected_lineup, team_name):
    """Create a mobile-friendly high-quality table format lineup image"""
    # Optimized dimensions for mobile viewing - larger fonts, smaller overall size
    width, height = 800, 1200  # Reduced size for mobile compatibility
    background_color = (255, 248, 220)  # Cornsilk (Cream) background
    table_bg_color = (255, 160, 122)  # Light Salmon table background
    header_bg_color = (255, 160, 122)  # Light Salmon header (matching table)
    text_color = (0, 0, 0)  # Bold black text
    header_text_color = (0, 0, 0)  # Bold black header text
    border_color = (0, 100, 200)  # Dark blue borders
    
    # Create high-resolution image
    img = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(img)
    
    # Font options available (in order of preference):
    # 1. Helvetica Bold - Clean, professional
    # 2. Arial Bold - Similar to Helvetica
    # 3. Times New Roman Bold - Classic serif
    # 4. Verdana Bold - Web-friendly sans-serif
    # 5. Georgia Bold - Readable serif
    # 6. Tahoma Bold - Compact sans-serif
    
    # Use proportionally larger fonts for mobile viewing
    try:
        # Try Helvetica Bold first - larger sizes for mobile compatibility
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48, index=1)  # Bold variant
        header_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32, index=1) # Bold variant
        text_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28, index=1)   # Bold variant
    except:
        try:
            # Try Helvetica regular (without bold)
            title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
            header_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
            text_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        except:
            try:
                # Try Arial Bold
                title_font = ImageFont.truetype("arialbd.ttf", 48)
                header_font = ImageFont.truetype("arialbd.ttf", 32)
                text_font = ImageFont.truetype("arialbd.ttf", 28)
            except:
                try:
                    # Try regular Arial
                    title_font = ImageFont.truetype("arial.ttf", 48)
                    header_font = ImageFont.truetype("arial.ttf", 32)
                    text_font = ImageFont.truetype("arial.ttf", 28)
                except:
                    # Fallback to default
                    title_font = ImageFont.load_default()
                    header_font = ImageFont.load_default()
                    text_font = ImageFont.load_default()
    
    # Draw only team name as heading
    team_text = f"Team: {team_name}"
    team_bbox = draw.textbbox((0, 0), team_text, font=title_font)
    team_width = team_bbox[2] - team_bbox[0]
    draw.text(((width - team_width) // 2, 150), team_text, fill=(0, 0, 0), font=title_font)
    
    # Table dimensions - adjusted for smaller image size
    table_x = 50
    table_y = 250
    table_width = width - 100
    row_height = 80  # Reduced row height
    col1_width = 120  # Round column
    col2_width = table_width - col1_width  # Player column
    
    # Draw table background
    table_height = row_height * 9  # 8 data rows + 1 header
    draw.rectangle([table_x, table_y, table_x + table_width, table_y + table_height], 
                   fill=table_bg_color, outline=border_color, width=4)
    
    # Draw header row
    draw.rectangle([table_x, table_y, table_x + table_width, table_y + row_height], 
                   fill=header_bg_color, outline=border_color, width=4)
    
    # Header text - adjusted positioning for smaller cells
    draw.text((table_x + 20, table_y + 25), "Round", fill=header_text_color, font=header_font)
    draw.text((table_x + col1_width + 20, table_y + 25), "Player(s)", fill=header_text_color, font=header_font)
    
    # Draw column separator line
    draw.line([table_x + col1_width, table_y, table_x + col1_width, table_y + table_height], 
              fill=border_color, width=4)
    
    # Draw data rows
    round_order = ["S1", "S2", "S3", "D1", "D2", "D3", "D4", "D5"]
    
    for i, round_name in enumerate(round_order):
        row_y = table_y + row_height * (i + 1)
        
        # Draw horizontal line
        draw.line([table_x, row_y, table_x + table_width, row_y], 
                  fill=border_color, width=2)
        
        # Round name - adjusted positioning for smaller cells
        draw.text((table_x + 20, row_y + 25), round_name, fill=text_color, font=text_font)
        
        # Player name(s) - adjusted positioning for smaller cells
        if round_name in selected_lineup:
            selection = selected_lineup[round_name]
            player_text = format_player_names(selection)
            draw.text((table_x + col1_width + 20, row_y + 25), player_text, fill=text_color, font=text_font)
        else:
            draw.text((table_x + col1_width + 20, row_y + 25), "Not selected", 
                     fill=(150, 150, 150), font=text_font)
    
    # Convert to bytes for download
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG', quality=95, dpi=(300, 300))
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
    # Download lineup as image button - direct download
    try:
        image_data = create_lineup_image(st.session_state.selected_lineup, team_name)
        st.download_button(
            label="📸 Download Lineup Image",
            data=image_data,
            file_name=f"MHTTF_Lineup_{team_name}.png",
            mime="image/png",
            type="primary"
        )
    except Exception as e:
        st.error(f"Error creating image: {str(e)}")
    
    st.divider()
    
    # Reset button
    if st.button("🔄 Reset All Selections", type="secondary"):
        st.session_state.selected_lineup = {}
        st.rerun()
