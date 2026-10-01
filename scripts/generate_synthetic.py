import argparse
import os
import sys
import time
import numpy as np
import pandas as pd
import duckdb

def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic money-mule transaction dataset.")
    parser.add_argument("--rows", type=int, default=2000000, help="Total number of transactions (default 2,000,000)")
    parser.add_argument("--accounts", type=int, default=25000, help="Total number of accounts (default 25,000)")
    parser.add_argument("--mules", type=int, default=1500, help="Total number of mule accounts (default 1,500)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    parser.add_argument("--out", type=str, default="data/raw/transactions.csv", help="Output transactions CSV path")
    return parser.parse_args()

def generate_synthetic_data(num_rows, num_accounts, num_mules, seed, out_csv_path):
    start_time = time.time()
    np.random.seed(seed)
    
    os.makedirs(os.path.dirname(out_csv_path), exist_ok=True)
    os.makedirs("data/raw", exist_ok=True)

    print(f"Generating synthetic dataset: {num_rows} rows, {num_accounts} accounts ({num_mules} mules)...")
    
    # 1. Generate Account Numbers (12-digit numbers)
    # Range 910000000000 - 910000000000 + num_accounts
    all_account_ids = np.arange(910000000001, 910000000001 + num_accounts, dtype=np.int64)
    all_account_strs = np.char.mod('%d', all_account_ids)
    
    # Reserve mule accounts & rings
    # Rings: ~100 rings
    num_rings = 100
    mule_indices = np.random.choice(num_accounts, size=num_mules, replace=False)
    mule_account_ids = all_account_ids[mule_indices]
    
    # Split mules into rings and layers: L1, L2, L3
    # Per ring: 1 victim (drawn from non-mule accounts), 3-5 L1, 5-8 L2, 3-5 L3
    victims = []
    ground_truth_records = []
    
    # Map account_id -> (is_mule, layer, ring_id, victim_account)
    ground_truth_map = {acc_id: (False, "none", -1, "") for acc_id in all_account_ids}
    
    non_mule_indices = np.setdiff1d(np.arange(num_accounts), mule_indices)
    victim_indices = np.random.choice(non_mule_indices, size=num_rings, replace=False)
    victim_account_ids = all_account_ids[victim_indices]
    
    # Assign mule accounts to rings
    mule_idx_offset = 0
    mules_per_ring = num_mules // num_rings
    
    ring_mule_structure = [] # list of dicts with ring metadata
    
    for r in range(num_rings):
        vic_acc = str(victim_account_ids[r])
        victims.append(vic_acc)
        
        # ring mules
        start_idx = r * mules_per_ring
        end_idx = (r + 1) * mules_per_ring if r < num_rings - 1 else num_mules
        ring_mules = mule_account_ids[start_idx:end_idx]
        
        # split into L1, L2, L3
        n_m = len(ring_mules)
        n_l1 = max(1, int(n_m * 0.25))
        n_l2 = max(1, int(n_m * 0.45))
        n_l3 = n_m - n_l1 - n_l2
        
        l1_accs = ring_mules[:n_l1]
        l2_accs = ring_mules[n_l1:n_l1+n_l2]
        l3_accs = ring_mules[n_l1+n_l2:]
        
        for acc in l1_accs:
            ground_truth_map[acc] = (True, "L1", r, vic_acc)
        for acc in l2_accs:
            ground_truth_map[acc] = (True, "L2", r, vic_acc)
        for acc in l3_accs:
            ground_truth_map[acc] = (True, "L3", r, vic_acc)
            
        ring_mule_structure.append({
            "ring_id": r,
            "victim": vic_acc,
            "L1": l1_accs,
            "L2": l2_accs,
            "L3": l3_accs
        })
        
    # Write ground_truth.csv and victims.csv
    gt_df = pd.DataFrame([
        {
            "account": str(acc_id),
            "is_mule": info[0],
            "layer": info[1],
            "ring_id": info[2],
            "victim_account": info[3]
        }
        for acc_id, info in ground_truth_map.items()
    ])
    gt_df.to_csv("data/raw/ground_truth.csv", index=False)
    
    victims_df = pd.DataFrame({"victim_account": victims})
    victims_df.to_csv("data/raw/victims.csv", index=False)
    print(f"Ground truth written: {len(gt_df)} accounts ({num_mules} mules), {len(victims)} victims.")

    # 2. Build Injected Mule Ring Transactions (~15% of dataset)
    # Mule transactions follow flow: Victim -> L1 -> L2 -> L3
    # Timestamp window: 15 days in seconds (15 * 86400 = 1,296,000 s)
    start_ts = 1788220800 # 2026-09-01 00:00:00 UTC timestamp simulation
    max_offset = 15 * 86400
    
    mule_txns = []
    
    # Generate ~200,000 mule transactions
    print("Simulating mule ring transaction flows (Victim -> L1 -> L2 -> L3)...")
    for ring in ring_mule_structure:
        r_id = ring["ring_id"]
        vic = ring["victim"]
        l1_list = ring["L1"]
        l2_list = ring["L2"]
        l3_list = ring["L3"]
        
        # Each ring has multiple fraud events over 15 days
        num_events = np.random.randint(15, 30)
        for _ in range(num_events):
            event_start = start_ts + np.random.randint(0, max_offset - 3600)
            stolen_amt = float(np.random.choice([49500, 99000, 150000, 250000, 500000, 1000000]))
            
            # Victim -> L1 (split across L1s)
            l1_chosen = np.random.choice(l1_list, size=min(len(l1_list), np.random.randint(1, len(l1_list)+1)), replace=False)
            amt_per_l1 = stolen_amt / len(l1_chosen)
            
            for l1 in l1_chosen:
                t1 = event_start + np.random.randint(0, 60)
                mule_txns.append((vic, str(l1), amt_per_l1, t1, "UPI", "Cyber Fraud Transfer", "103.21.12.45", "Android"))
                
                # L1 -> L2 (rapid forwarding in 3-15 minutes, >=90% amount)
                l2_chosen = np.random.choice(l2_list, size=min(len(l2_list), np.random.randint(2, max(3, len(l2_list)+1))), replace=False)
                forward_l1_amt = amt_per_l1 * np.random.uniform(0.92, 0.98)
                amt_per_l2 = forward_l1_amt / len(l2_chosen)
                
                for l2 in l2_chosen:
                    t2 = t1 + np.random.randint(180, 900) # 3 - 15 mins
                    mule_txns.append((str(l1), str(l2), amt_per_l2, t2, "IMPS", "Immediate Fund Move", "117.55.201.12", "Android"))
                    
                    # L2 -> L3 (rapid forwarding in 3-15 minutes, >=90% amount)
                    if len(l3_list) > 0:
                        l3_chosen = np.random.choice(l3_list, size=min(len(l3_list), np.random.randint(1, max(2, len(l3_list)+1))), replace=False)
                        forward_l2_amt = amt_per_l2 * np.random.uniform(0.92, 0.98)
                        amt_per_l3 = forward_l2_amt / len(l3_chosen)
                        
                        for l3 in l3_chosen:
                            t3 = t2 + np.random.randint(180, 900)
                            ip_prefix = np.random.choice(["185.220.101.", "194.165.16."])
                            foreign_ip = ip_prefix + str(np.random.randint(1, 254))
                            device = np.random.choice(["Web_Emulator", "Linux_Script"])
                            narration = np.random.choice(["Crypto P2P USDT", "Wallet Cashout", "ATM Withdrawal", "P2P Crypto Exchange"])
                            mule_txns.append((str(l2), str(l3), amt_per_l3, t3, "NEFT", narration, foreign_ip, device))

    num_mule_txns = len(mule_txns)
    print(f"Generated {num_mule_txns} injected mule transactions.")
    
    # 3. Vectorized Normal Transactions Generation
    num_normal_txns = num_rows - num_mule_txns
    print(f"Generating {num_normal_txns} vectorized background/normal & noise transactions...")
    
    # Select random senders and receivers from all accounts
    sender_idx = np.random.randint(0, num_accounts, size=num_normal_txns)
    receiver_idx = np.random.randint(0, num_accounts, size=num_normal_txns)
    
    # Ensure sender != receiver
    same_mask = sender_idx == receiver_idx
    receiver_idx[same_mask] = (receiver_idx[same_mask] + 1) % num_accounts
    
    # High degree hubs (first 200 normal accounts are hubs like employers, merchants)
    hubs = np.arange(200, dtype=np.int64)
    # Inject 20% of transactions to hubs
    hub_mask = np.random.rand(num_normal_txns) < 0.20
    receiver_idx[hub_mask] = np.random.choice(hubs, size=np.sum(hub_mask))
    
    senders = all_account_strs[sender_idx]
    receivers = all_account_strs[receiver_idx]
    
    # IFSC codes
    ifsc_prefix = np.array(["SBIN0001234", "HDFC0005678", "ICIC0009101", "BARB0001112", "AXIS0003344", "PUNB0001212", "KKBK0004545", "CANB0007878"])
    s_ifsc = np.random.choice(ifsc_prefix, size=num_normal_txns)
    r_ifsc = np.random.choice(ifsc_prefix, size=num_normal_txns)
    
    # Amounts: mixture of standard (100 - 25000) and structured amounts (48500, 49500, 49900, 98500, 99500)
    base_amounts = np.random.exponential(scale=3500.0, size=num_normal_txns) + 50.0
    base_amounts = np.clip(base_amounts, 50.0, 450000.0)
    
    # Inject structuring noise (5% of normal transactions)
    struct_mask = np.random.rand(num_normal_txns) < 0.05
    struct_values = np.random.choice([48900.0, 49500.0, 49800.0, 49950.0, 98500.0, 99000.0, 99900.0], size=np.sum(struct_mask))
    base_amounts[struct_mask] = struct_values
    
    # Timestamps spread over 15 days
    ts_offsets = np.random.randint(0, max_offset, size=num_normal_txns)
    normal_timestamps = start_ts + ts_offsets
    
    # Payment modes
    modes = np.array(["UPI", "IMPS", "NEFT", "RTGS"])
    mode_probs = [0.70, 0.15, 0.10, 0.05]
    p_modes = np.random.choice(modes, size=num_normal_txns, p=mode_probs)
    
    # Narrations
    narrations_pool = np.array([
        "UPI Transfer", "Salary Credit", "Merchant Payment", "Bill Payment",
        "P2P Transfer", "Grocery Store", "Rent Payment", "Utility Bill", "Online Shopping"
    ])
    narrations = np.random.choice(narrations_pool, size=num_normal_txns)
    
    # Domestic IPs
    ip_base = np.array(["49.36.", "103.21.", "117.55.", "157.33.", "106.20.", "42.104."])
    ip_p1 = np.random.choice(ip_base, size=num_normal_txns)
    ip_p2 = np.random.randint(1, 254, size=num_normal_txns).astype(str)
    ip_p3 = np.random.randint(1, 254, size=num_normal_txns).astype(str)
    ips = np.char.add(ip_p1, np.char.add(ip_p2, np.char.add(".", ip_p3)))
    
    # Devices
    devices_pool = np.array(["Android", "iOS", "Windows_Browser"])
    devices = np.random.choice(devices_pool, size=num_normal_txns, p=[0.60, 0.25, 0.15])

    # Construct Pandas / Arrow DataFrames & merge
    print("Assembling final dataset...")
    
    # Convert timestamps to YYYY-MM-DD HH:MM:SS strings
    normal_ts_strs = pd.to_datetime(normal_timestamps, unit='s').strftime('%Y-%m-%d %H:%M:%S').values
    
    # Mule dataframe
    mule_senders = [m[0] for m in mule_txns]
    mule_receivers = [m[1] for m in mule_txns]
    mule_amounts = [m[2] for m in mule_txns]
    mule_ts_sec = [m[3] for m in mule_txns]
    mule_modes = [m[4] for m in mule_txns]
    mule_narrs = [m[5] for m in mule_txns]
    mule_ips = [m[6] for m in mule_txns]
    mule_devs = [m[7] for m in mule_txns]
    
    mule_s_ifsc = np.random.choice(ifsc_prefix, size=num_mule_txns)
    mule_r_ifsc = np.random.choice(ifsc_prefix, size=num_mule_txns)
    mule_ts_strs = pd.to_datetime(mule_ts_sec, unit='s').strftime('%Y-%m-%d %H:%M:%S').values
    
    # Combine normal + mule arrays
    all_senders = np.concatenate([senders, mule_senders])
    all_receivers = np.concatenate([receivers, mule_receivers])
    all_s_ifsc = np.concatenate([s_ifsc, mule_s_ifsc])
    all_r_ifsc = np.concatenate([r_ifsc, mule_r_ifsc])
    all_amounts = np.round(np.concatenate([base_amounts, mule_amounts]), 2)
    all_ts = np.concatenate([normal_ts_strs, mule_ts_strs])
    all_modes = np.concatenate([p_modes, mule_modes])
    all_narrs = np.concatenate([narrations, mule_narrs])
    all_ips = np.concatenate([ips, mule_ips])
    all_devs = np.concatenate([devices, mule_devs])
    
    # Generate Transaction IDs
    txn_ids = np.char.mod('TXN%010d', np.arange(1, num_rows + 1))
    
    # Shuffle order so mules are intermixed with normal transactions chronologically
    sort_idx = np.argsort(all_ts)
    
    df = pd.DataFrame({
        "Transaction_ID": txn_ids[sort_idx],
        "Sender_Account": all_senders[sort_idx],
        "Receiver_Account": all_receivers[sort_idx],
        "Sender_IFSC": all_s_ifsc[sort_idx],
        "Receiver_IFSC": all_r_ifsc[sort_idx],
        "Amount": all_amounts[sort_idx],
        "Timestamp": all_ts[sort_idx],
        "Payment_Mode": all_modes[sort_idx],
        "Narration": all_narrs[sort_idx],
        "IP_Address": all_ips[sort_idx],
        "Device_Type": all_devs[sort_idx]
    })

    # Fast export via DuckDB to CSV
    print(f"Exporting {len(df)} rows to {out_csv_path} via DuckDB...")
    con = duckdb.connect(database=':memory:')
    con.register('df_view', df)
    con.execute(f"COPY df_view TO '{out_csv_path}' (HEADER, DELIMITER ',')")
    con.close()
    
    elapsed = time.time() - start_time
    print(f"SUCCESS: Generated {len(df)} rows in {elapsed:.2f} seconds!")

if __name__ == "__main__":
    args = parse_args()
    generate_synthetic_data(args.rows, args.accounts, args.mules, args.seed, args.out)
