import streamlit as st
import pandas as pd
import math
from src.database import SessionLocal, Article, FeedSource, Keyword, engine
from src.train_model import train # Import the trainer function directly
from src.scheduler import fetch_feeds
import time
from sqlalchemy import text

st.set_page_config(page_title="RSS Intel Monitor", layout="wide")

def get_db():
    return SessionLocal()

# --- Sidebar Navigation ---
st.sidebar.title("News Monitor")
page = st.sidebar.radio("Navigation", ["Dashboard", "Training Data", "Configuration"])

session = get_db()

# ================= DASHBOARD =================
# ================= DASHBOARD =================
if page == "Dashboard":
    col_title, col_btn = st.columns([3, 1])
    col_title.title("🚨 Live News")
    
    # The Force Run Button
    if col_btn.button("🔄 Force Fetch Feeds"):
        with st.spinner("Fetching latest intel... this may take a moment."):
            fetch_feeds(source="User Force") 
            st.success("Fetch complete!")
            time.sleep(1)
            st.rerun()

    # --- View Mode Selection ---
    # We added "Acknowledged" to the options
    view_mode = st.radio(
        "Filter", 
        ["High Priority (Inbox)", "Acknowledged (Confirmed)", "All Articles (Archive)"], 
        horizontal=True
    )
    
    # --- VIEW 1: HIGH PRIORITY (INBOX) ---
    if view_mode == "High Priority (Inbox)":
        st.caption("Action Required: Items bubbled up by Keywords/ML waiting for review.")
        
        # FILTER: bubbled=True AND feedback=0 (Unreviewed)
        articles = session.query(Article).filter(
            Article.is_bubbled == True, 
            Article.human_feedback == 0
        ).order_by(Article.score.desc()).all()

        if not articles:
            st.success("🎉 You are all caught up! No pending alerts.")

        for art in articles:
            # Score Color Code
            score_color = "red" if art.score > 80 else "orange" if art.score > 50 else "blue"
            
            with st.expander(f":{score_color}[[{int(art.score)}]] {art.title}", expanded=True):
                col_meta, col_link = st.columns([3, 1])
                date_str = art.published_date.strftime('%Y-%m-%d %H:%M') if art.published_date else "Unknown"
                col_meta.caption(f"📅 {date_str} | 📡 {art.source} | 🏷️ {art.keywords_found}")
                col_link.markdown(f"[Read Article]({art.link})")
                
                st.write(art.summary)
                
                # ACTION BUTTONS
                c1, c2, c3 = st.columns([1, 1, 4])
                
                # Confirm -> Moves to "Acknowledged" tab
                if c1.button("✅ Acknowledge", key=f"ack_{art.id}"):
                    art.human_feedback = 2  # 2 = Confirmed/Important
                    session.commit()
                    st.rerun()
                
                # Dismiss -> Vanishes (only visible in Training Data)
                if c2.button("❌ Dismiss", key=f"dis_{art.id}"):
                    art.human_feedback = 1  # 1 = Dismissed/Noise
                    session.commit()
                    st.rerun()

    # --- VIEW 2: ACKNOWLEDGED (CONFIRMED) ---
    elif view_mode == "Acknowledged (Confirmed)":
        st.subheader("✅ Confirmed Intelligence")
        st.caption("Articles you (or the AI) have marked as valid threats.")
        
        # FILTER: feedback=2 (Confirmed)
        # We use pagination here too because this list will grow forever
        total_ack = session.query(Article).filter(Article.human_feedback == 2).count()
        
        # Pagination Controls
        col_c, col_i = st.columns([1, 4])
        limit = col_c.selectbox("Show", [20, 50, 100], key="ack_limit")
        
        articles = session.query(Article)\
            .filter(Article.human_feedback == 2)\
            .order_by(Article.published_date.desc())\
            .limit(limit)\
            .all()
        
        if not articles:
            st.info("No acknowledged articles yet.")

        for art in articles:
            with st.expander(f"✅ [[{int(art.score)}]] {art.title}"):
                st.caption(f"Source: {art.source}")
                st.write(art.summary)
                st.markdown(f"[Read Article]({art.link})")
                
                # Undo Button (In case of mis-click)
                if st.button("Re-open (Move to Inbox)", key=f"undo_{art.id}"):
                    art.human_feedback = 0
                    session.commit()
                    st.rerun()

    # --- VIEW 3: ALL ARTICLES (ARCHIVE) ---
    # --- VIEW 3: ALL ARTICLES (ARCHIVE) ---
    elif view_mode == "All Articles (Archive)":
        st.subheader("🗄️ Feed Archive")
        
        # 1. Calculate Total Pages
        total_articles = session.query(Article).count()
        
        # 2. Controls
        col_controls, col_info = st.columns([1, 3])
        
        with col_controls:
            items_per_page = st.selectbox("Articles per page", [20, 50, 100], index=0)
            
        total_pages = math.ceil(total_articles / items_per_page)
        if total_pages < 1: total_pages = 1
        
        with col_controls:
            current_page = st.number_input(
                "Page Number", 
                min_value=1, 
                max_value=total_pages, 
                value=1
            )
            
        with col_info:
            st.write("") 
            st.write("") 
            st.caption(f"Showing page **{current_page}** of **{total_pages}** ({total_articles} total articles)")

        # 3. Efficient Query
        offset = (current_page - 1) * items_per_page
        
        articles = session.query(Article)\
            .order_by(Article.published_date.desc())\
            .offset(offset)\
            .limit(items_per_page)\
            .all()
        
        st.divider()

        # 4. Display Loop
        for art in articles:
            score_color = "red" if art.score > 50 else "orange" if art.score > 20 else "gray"
            
            with st.expander(f":{score_color}[[{int(art.score)}]] {art.title}"):
                col_meta, col_link = st.columns([3, 1])
                date_str = art.published_date.strftime('%Y-%m-%d %H:%M') if art.published_date else "Unknown"
                col_meta.caption(f"📅 {date_str} | 📡 {art.source}")
                col_link.markdown(f"[Read Article]({art.link})")
                
                st.write(art.summary)
                
                # --- FIX: Define columns c1/c2 before using them ---
                c1, c2 = st.columns([1, 6])
                
                # Promote to Inbox
                if c1.button("Mark Critical", key=f"archive_crit_{art.id}"):
                    art.human_feedback = 0 # Reset feedback so it appears in Inbox
                    art.is_bubbled = True 
                    session.commit()
                    st.toast(f"Promoted '{art.title}' to Inbox!")
                    time.sleep(1)
                    st.rerun()

# ================= TRAINING DATA =================
elif page == "Training Data":
    st.title("🧠 Machine Learning Lab")
    
    # 1. Stats
    count_pos = session.query(Article).filter(Article.human_feedback == 2).count()
    count_neg = session.query(Article).filter(Article.human_feedback == 1).count()
    total = count_pos + count_neg
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Samples", total)
    c2.metric("Positives (Keep)", count_pos)
    c3.metric("Negatives (Dismiss)", count_neg)
    
    st.divider()
    
    # 2. Retrain Button
    st.subheader("Model Management")
    if st.button("🚀 Retrain Model Now", type="primary"):
        if total < 10:
            st.error("Not enough data! Please review at least 10 articles.")
        else:
            with st.spinner("Training neural pathways..."):
                try:
                    train() # Calls your python script
                    st.success("Model retrained successfully! The next scheduled fetch will use the new brain.")
                except Exception as e:
                    st.error(f"Training failed: {e}")

    st.divider()
    st.subheader("Labeled Dataset")
    df = pd.read_sql(session.query(Article).filter(Article.human_feedback != 0).statement, session.bind)
    st.dataframe(df)

# ================= CONFIGURATION =================
elif page == "Configuration":
    st.title("⚙️ System Settings")
    
    tab1, tab2, tab3 = st.tabs(["Keywords (Rule-Based)", "RSS Sources", "Danger Zone"])
    
    # --- Tab 1: Keywords ---
    with tab1:
        st.subheader("Manage Keywords")
        st.info("Format: `keyword, weight` (one per line). If weight is omitted, defaults to 10.")
        
        # Bulk Add Form
        with st.form("bulk_kw"):
            raw_text = st.text_area("Bulk Add Keywords", placeholder="zero-day, 80\ncritical patch, 50\nransomware")
            if st.form_submit_button("Add Keywords"):
                lines = raw_text.split('\n')
                added_count = 0
                skipped_count = 0
                
                for line in lines:
                    if not line.strip(): continue
                    parts = line.split(',')
                    word = parts[0].strip().lower()
                    weight = 10
                    if len(parts) > 1:
                        try:
                            weight = int(parts[1].strip())
                        except ValueError:
                            pass 
                    
                    exists = session.query(Keyword).filter_by(word=word).first()
                    if not exists:
                        session.add(Keyword(word=word, weight=weight))
                        added_count += 1
                    else:
                        skipped_count += 1
                
                session.commit()
                if added_count > 0: st.success(f"✅ Added {added_count} keywords.")
                if skipped_count > 0: st.warning(f"⚠️ Skipped {skipped_count} duplicates.")
                st.rerun()
        
        st.divider()
        
        # List Keywords
        st.write("### Active Keywords")
        keywords = session.query(Keyword).order_by(Keyword.weight.desc()).all()
        for k in keywords:
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.code(k.word)
            col2.write(f"Weight: **{k.weight}**")
            if col3.button("🗑️", key=f"del_kw_{k.id}"):
                session.delete(k)
                session.commit()
                st.rerun()

    # --- Tab 2: Sources ---
    with tab2:
        st.subheader("Manage RSS Feeds")
        st.info("Format: `URL, Name` (one per line).")
        
        with st.form("bulk_feed"):
            raw_text = st.text_area("Bulk Add Feeds", placeholder="https://site.com/feed, Security Weekly")
            if st.form_submit_button("Add Sources"):
                lines = raw_text.split('\n')
                added_count = 0
                skipped_count = 0
                for line in lines:
                    if not line.strip(): continue
                    parts = line.split(',')
                    url = parts[0].strip()
                    name = parts[1].strip() if len(parts) > 1 else "New Feed"
                    
                    exists = session.query(FeedSource).filter_by(url=url).first()
                    if not exists:
                        session.add(FeedSource(url=url, name=name))
                        added_count += 1
                    else:
                        skipped_count += 1
                
                session.commit()
                if added_count > 0: st.success(f"✅ Added {added_count} feeds.")
                st.rerun()

        st.divider()
        st.write("### Active Feeds")
        sources = session.query(FeedSource).all()
        for s in sources:
            with st.expander(f"{s.name}"):
                st.text(s.url)
                if st.button("Delete Feed", key=f"del_src_{s.id}"):
                    session.delete(s)
                    session.commit()
                    st.rerun()

 # --- DANGER ZONE (Inside Tab 3) ---
    with tab3:    
        st.divider()
        with st.expander("⚠️ Danger Zone", expanded=False):
            st.error("These actions are irreversible!")
            col1, col2 = st.columns(2)
            
            # Action 1: Clear Articles
            with col1:
                st.write("**Clear History**")
                st.caption("Deletes articles but keeps Feeds/Keywords.")
                if st.button("🗑️ Delete All Articles"):
                    try:
                        session.execute(text("TRUNCATE TABLE articles RESTART IDENTITY CASCADE;"))
                        session.commit()
                        st.success("All articles deleted.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

            # Action 2: Factory Reset
            with col2:
                st.write("**Factory Reset**")
                st.caption("Wipes EVERYTHING.")
                if st.button("☢️ FULL RESET"):
                    try:
                        session.execute(text("TRUNCATE TABLE articles, feed_sources, keywords RESTART IDENTITY CASCADE;"))
                        session.commit()
                        st.success("System reset.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

session.close()