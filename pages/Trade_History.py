import streamlit as st
import pandas as pd
from database import load_trades, export_trades_csv, get_trade_count, delete_trade, save_trade

st.set_page_config(
    page_title="Trade History",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PAGE TITLE ---
st.title("📜 Trade History")
st.markdown("Comprehensive view of all logged trades with export functionality.")

# --- TRADE COUNT METRICS ---
trade_count = get_trade_count()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Trades", trade_count)

# Load trade history from database
trades_df = load_trades()

if not trades_df.empty:
    # Calculate additional metrics
    buy_count = len(trades_df[trades_df['signal'] == 'BUY'])
    sell_count = len(trades_df[trades_df['signal'] == 'SELL'])
    total_capital_at_risk = pd.to_numeric(trades_df['capital_at_risk'], errors='coerce').fillna(0).sum()
    
    with col2:
        st.metric("BUY Signals", buy_count)
    with col3:
        st.metric("SELL Signals", sell_count)
    
    st.metric("Total Capital Deployed", f"${total_capital_at_risk:,.2f}")
    
    # --- FILTERS ---
    st.subheader("🔍 Filter Trades")
    
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    
    with col_filter1:
        # Ticker filter
        all_tickers = ['All'] + sorted(trades_df['ticker'].unique().tolist())
        selected_ticker = st.selectbox("Filter by Ticker", all_tickers)
    
    with col_filter2:
        # Signal filter
        signal_options = ['All', 'BUY', 'SELL']
        selected_signal = st.selectbox("Filter by Signal", signal_options)
    
    with col_filter3:
        # Sort options
        sort_options = ['Date (Newest First)', 'Date (Oldest First)', 'Entry Price (High to Low)', 'Entry Price (Low to High)']
        selected_sort = st.selectbox("Sort By", sort_options)
    
    # Apply filters
    filtered_df = trades_df.copy()
    
    if selected_ticker != 'All':
        filtered_df = filtered_df[filtered_df['ticker'] == selected_ticker]
    
    if selected_signal != 'All':
        filtered_df = filtered_df[filtered_df['signal'] == selected_signal]
    
    # Apply sorting
    if selected_sort == 'Date (Newest First)':
        filtered_df = filtered_df.sort_values('date', ascending=False)
    elif selected_sort == 'Date (Oldest First)':
        filtered_df = filtered_df.sort_values('date', ascending=True)
    elif selected_sort == 'Entry Price (High to Low)':
        filtered_df = filtered_df.sort_values('entry_price', ascending=False)
    elif selected_sort == 'Entry Price (Low to High)':
        filtered_df = filtered_df.sort_values('entry_price', ascending=True)
    
    # --- TRADE HISTORY TABLE ---
    st.subheader("📊 Trade Records")
    display_df = filtered_df.copy()
    display_df['entry_price'] = pd.to_numeric(display_df['entry_price'], errors='coerce').map(lambda x: f"${x:,.2f}" if pd.notna(x) else "-")
    display_df['capital_at_risk'] = pd.to_numeric(display_df['capital_at_risk'], errors='coerce').map(lambda x: f"${x:,.2f}" if pd.notna(x) else "-")
    display_df['volume'] = pd.to_numeric(display_df['volume'], errors='coerce').map(lambda x: f"{x:,.2f}" if pd.notna(x) else "-")
    st.dataframe(display_df, use_container_width=True, height=400)
    
    # --- EXPORT SECTION ---
    st.subheader("💾 Export Data")
    
    col_export1, col_export2 = st.columns(2)
    
    with col_export1:
        # Export filtered data
        if st.button("📥 Export Filtered Data to CSV", key="export_filtered"):
            filename = f"trades_export_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
            try:
                # Export filtered dataframe
                filtered_df.to_csv(filename, index=False)
                st.success(f"Exported {len(filtered_df)} trades to `{filename}`")
                
                # Provide download button
                with open(filename, 'r') as f:
                    st.download_button(
                        label="⬇️ Download CSV File",
                        data=f.read(),
                        file_name=filename,
                        mime='text/csv'
                    )
            except Exception as e:
                st.error(f"❌ Error exporting data: {str(e)}")
    
    with col_export2:
        # Export all data using database function
        if st.button("📥 Export All Trades to CSV", key="export_all"):
            filename = f"trades_backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
            try:
                export_trades_csv(filename)
                st.success(f"✅ Exported all {trade_count} trades to `{filename}`")
                
                # Provide download button
                with open(filename, 'r') as f:
                    st.download_button(
                        label="⬇️ Download CSV File",
                        data=f.read(),
                        file_name=filename,
                        mime='text/csv'
                    )
            except Exception as e:
                st.error(f"❌ Error exporting data: {str(e)}")
    
    # --- IMPORT SECTION ---
    st.subheader("📤 Restore from Backup")
    st.markdown("Upload a previously exported CSV file to restore your trade history.")
    
    uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'], key="import_csv")
    
    if uploaded_file is not None:
        try:
            # Read the uploaded CSV
            import_df = pd.read_csv(uploaded_file)
            
            # Validate required columns
            required_cols = ['date', 'ticker', 'signal', 'entry_price', 'volume', 'capital_at_risk']
            missing_cols = [col for col in required_cols if col not in import_df.columns]
            
            if missing_cols:
                st.error(f"❌ Missing columns in CSV: {', '.join(missing_cols)}")
                st.info(f"Required columns: {', '.join(required_cols)}")
            else:
                # Preview the data to be imported
                st.write("### 📋 Preview - Trades to Import")
                st.dataframe(import_df, use_container_width=True, height=200)
                
                # Show import stats
                col_import1, col_import2, col_import3 = st.columns(3)
                with col_import1:
                    st.metric("Trades to Import", len(import_df))
                with col_import2:
                    buy_count_import = len(import_df[import_df['signal'] == 'BUY'])
                    st.metric("BUY Trades", buy_count_import)
                with col_import3:
                    sell_count_import = len(import_df[import_df['signal'] == 'SELL'])
                    st.metric("SELL Trades", sell_count_import)
                
                # Confirmation button
                if st.button("✅ Import All Trades", key="confirm_import", type="primary"):
                    try:
                        successful_imports = 0
                        failed_imports = 0
                        
                        with st.spinner("Importing trades..."):
                            for idx, row in import_df.iterrows():
                                try:
                                    trade_id = save_trade(
                                        date=str(row['date']),
                                        ticker=str(row['ticker']).upper(),
                                        signal=str(row['signal']).upper(),
                                        entry_price=float(row['entry_price']),
                                        volume=float(row['volume']),
                                        capital_at_risk=float(row['capital_at_risk'])
                                    )
                                    if trade_id:
                                        successful_imports += 1
                                    else:
                                        failed_imports += 1
                                except Exception as e:
                                    st.warning(f"Row {idx + 1}: {str(e)}")
                                    failed_imports += 1
                        
                        # Import summary
                        st.success(f"✅ Import complete! {successful_imports} trades imported successfully.")
                        if failed_imports > 0:
                            st.warning(f"⚠️ {failed_imports} trades failed to import.")
                        
                        st.rerun()  # Refresh page to show new trades
                    
                    except Exception as e:
                        st.error(f"Error during import: {str(e)}")
        
        except Exception as e:
            st.error(f"Error reading CSV file: {str(e)}")

    # --- DELETE TRADES SECTION (Optional - Admin) ---
    with st.expander("⚠️ Advanced: Delete Trades", expanded=False):
        st.warning("WARNING: Deleting trades is permanent and cannot be undone!")
        
        col_delete1, col_delete2 = st.columns(2)
        
        with col_delete1:
            trade_id_to_delete = st.number_input(
                "Trade ID to Delete", 
                min_value=1, 
                value=1, 
                step=1,
                key="delete_id"
            )
        
        with col_delete2:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("🗑️ Delete Trade", key="delete_btn", type="secondary"):
                try:
                    delete_trade(trade_id_to_delete)
                    st.success(f"✅ Trade #{trade_id_to_delete} deleted successfully!")
                    st.rerun()  # Refresh the page to show updated data
                except Exception as e:
                    st.error(f"❌ Error deleting trade: {str(e)}")

else:
    # No trades in database
    st.info("📊 No trades logged yet. Visit the Dashboard page to start logging trades!")
    st.markdown("---")
    st.markdown("### 🚀 Getting Started")
    st.markdown("""
    1. Navigate to the Dashboard page using the sidebar
    2. Configure your ticker symbol and capital settings
    3. Analyze the market and wait for trading signals
    4. Log trades manually
    5. Return here to view your trade history
    """)
