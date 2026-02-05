"""
Data Export Module
Export data ke berbagai format: CSV, Excel, JSON Lines, GraphML, GEXF
"""

import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class DataExporter:
    """
    Export scraping results ke berbagai format
    
    Usage:
        exporter = DataExporter(output_dir="./output")
        
        # Export users ke CSV
        exporter.to_csv(users, "followers.csv")
        
        # Export ke Excel
        exporter.to_excel(users, "followers.xlsx")
        
        # Export network ke GraphML (untuk Gephi)
        exporter.to_graphml(users, "network.graphml")
    """
    
    def __init__(self, output_dir: str = "."):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    # ==================== CSV EXPORT ====================
    
    def to_csv(self, data: List[Dict], filename: str) -> str:
        """Export ke CSV format"""
        if not data:
            print("[Export] No data to export")
            return ""
        
        filepath = self.output_dir / filename
        
        # Get all unique keys
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())
        fieldnames = sorted(all_keys)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        print(f"[Export] CSV saved: {filepath}")
        return str(filepath)
    
    # ==================== JSON LINES EXPORT ====================
    
    def to_jsonl(self, data: List[Dict], filename: str) -> str:
        """Export ke JSON Lines format (satu JSON per baris)"""
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        print(f"[Export] JSONL saved: {filepath}")
        return str(filepath)
    
    # ==================== EXCEL EXPORT ====================
    
    def to_excel(self, data: List[Dict], filename: str) -> str:
        """Export ke Excel format (requires openpyxl)"""
        try:
            from openpyxl import Workbook
        except ImportError:
            print("[Export] openpyxl not installed. Run: pip install openpyxl")
            # Fallback to CSV
            return self.to_csv(data, filename.replace('.xlsx', '.csv'))
        
        if not data:
            print("[Export] No data to export")
            return ""
        
        filepath = self.output_dir / filename
        wb = Workbook()
        ws = wb.active
        ws.title = "TikTok Data"
        
        # Headers
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())
        headers = sorted(all_keys)
        ws.append(headers)
        
        # Data rows
        for item in data:
            row = [item.get(key, '') for key in headers]
            ws.append(row)
        
        # Auto-width columns
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        wb.save(filepath)
        print(f"[Export] Excel saved: {filepath}")
        return str(filepath)
    
    # ==================== GRAPHML EXPORT ====================
    
    def to_graphml(
        self, 
        users: List[Dict], 
        filename: str,
        edges: Optional[List[tuple]] = None
    ) -> str:
        """
        Export ke GraphML format (untuk Gephi, yEd, dll)
        
        Args:
            users: List of user dicts dengan minimal 'username'
            filename: Output filename
            edges: Optional list of (source, target) tuples
        """
        filepath = self.output_dir / filename
        
        # Build nodes
        nodes_xml = []
        for i, user in enumerate(users):
            username = user.get('username', f'user_{i}')
            label = user.get('nickname', username)
            
            # Attributes
            attrs = []
            for key, value in user.items():
                if key not in ['username', 'nickname', 'profile_url']:
                    attrs.append(f'      <data key="{key}">{self._escape_xml(value)}</data>')
            
            node_xml = f'''    <node id="{username}">
      <data key="label">{self._escape_xml(label)}</data>
{chr(10).join(attrs) if attrs else ''}
    </node>'''
            nodes_xml.append(node_xml)
        
        # Build edges
        edges_xml = []
        if edges:
            for i, (source, target) in enumerate(edges):
                edge_xml = f'    <edge id="e{i}" source="{source}" target="{target}"/>'
                edges_xml.append(edge_xml)
        
        # Build full GraphML
        graphml = f'''<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="label" for="node" attr.name="label" attr.type="string"/>
  <key id="depth" for="node" attr.name="depth" attr.type="int"/>
  <key id="followers" for="node" attr.name="followers" attr.type="int"/>
  <key id="influence_score" for="node" attr.name="influence_score" attr.type="double"/>
  <key id="visit_count" for="node" attr.name="visit_count" attr.type="int"/>
  <key id="community" for="node" attr.name="community" attr.type="string"/>
  <graph id="TikTokNetwork" edgedefault="directed">
{chr(10).join(nodes_xml)}
{chr(10).join(edges_xml)}
  </graph>
</graphml>'''
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(graphml)
        
        print(f"[Export] GraphML saved: {filepath}")
        return str(filepath)
    
    # ==================== GEXF EXPORT ====================
    
    def to_gexf(
        self, 
        users: List[Dict], 
        filename: str,
        edges: Optional[List[tuple]] = None
    ) -> str:
        """Export ke GEXF format (Gephi native format)"""
        filepath = self.output_dir / filename
        timestamp = datetime.now().isoformat()
        
        # Build nodes
        nodes_xml = []
        for i, user in enumerate(users):
            username = user.get('username', f'user_{i}')
            label = user.get('nickname', username)
            
            # Attvalues
            attvalues = []
            attr_map = {
                'depth': '0',
                'followers': '1', 
                'influence_score': '2',
                'visit_count': '3',
                'community': '4'
            }
            
            for key, attr_id in attr_map.items():
                if key in user:
                    attvalues.append(f'          <attvalue for="{attr_id}" value="{user[key]}"/>')
            
            node_xml = f'''      <node id="{username}" label="{self._escape_xml(label)}">
        <attvalues>
{chr(10).join(attvalues) if attvalues else ''}
        </attvalues>
      </node>'''
            nodes_xml.append(node_xml)
        
        # Build edges
        edges_xml = []
        if edges:
            for i, (source, target) in enumerate(edges):
                edges_xml.append(f'      <edge id="{i}" source="{source}" target="{target}"/>')
        
        gexf = f'''<?xml version="1.0" encoding="UTF-8"?>
<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">
  <meta lastmodifieddate="{timestamp}">
    <creator>TikTok Scraper v3.0</creator>
    <description>TikTok Social Network</description>
  </meta>
  <graph mode="static" defaultedgetype="directed">
    <attributes class="node">
      <attribute id="0" title="depth" type="integer"/>
      <attribute id="1" title="followers" type="integer"/>
      <attribute id="2" title="influence_score" type="float"/>
      <attribute id="3" title="visit_count" type="integer"/>
      <attribute id="4" title="community" type="string"/>
    </attributes>
    <nodes>
{chr(10).join(nodes_xml)}
    </nodes>
    <edges>
{chr(10).join(edges_xml)}
    </edges>
  </graph>
</gexf>'''
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(gexf)
        
        print(f"[Export] GEXF saved: {filepath}")
        return str(filepath)
    
    # ==================== STATISTICS ====================
    
    def generate_stats(self, users: List[Dict]) -> Dict[str, Any]:
        """Generate statistics dari data"""
        if not users:
            return {}
        
        stats = {
            'total_users': len(users),
            'timestamp': datetime.now().isoformat(),
        }
        
        # Follower stats
        followers = [u.get('followers', u.get('follower_count', 0)) for u in users]
        followers = [f for f in followers if isinstance(f, (int, float))]
        if followers:
            stats['followers'] = {
                'total': sum(followers),
                'average': sum(followers) / len(followers),
                'max': max(followers),
                'min': min(followers)
            }
        
        # Depth distribution
        depths = [u.get('depth', 0) for u in users]
        depth_dist = {}
        for d in depths:
            depth_dist[d] = depth_dist.get(d, 0) + 1
        stats['depth_distribution'] = depth_dist
        
        # Influence score stats (if present)
        scores = [u.get('influence_score', 0) for u in users if 'influence_score' in u]
        if scores:
            stats['influence'] = {
                'top_score': max(scores),
                'average_score': sum(scores) / len(scores)
            }
        
        # Community stats (if present)
        communities = set(u.get('community') for u in users if 'community' in u)
        if communities:
            stats['communities'] = {
                'count': len(communities),
                'names': list(communities)[:10]  # First 10
            }
        
        return stats
    
    def save_stats(self, users: List[Dict], filename: str) -> str:
        """Generate and save statistics to JSON"""
        stats = self.generate_stats(users)
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
        
        print(f"[Export] Stats saved: {filepath}")
        return str(filepath)
    
    # ==================== HELPERS ====================
    
    def _escape_xml(self, value: Any) -> str:
        """Escape special XML characters"""
        if value is None:
            return ""
        s = str(value)
        return (s
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def export_data(
    data: List[Dict],
    filename: str,
    format: str = "csv",
    output_dir: str = "."
) -> str:
    """
    Helper function untuk export data
    
    Args:
        data: List of dicts to export
        filename: Base filename (extension will be added)
        format: "csv", "excel", "jsonl", "graphml", "gexf"
        output_dir: Output directory
    """
    exporter = DataExporter(output_dir)
    
    if format == "csv":
        return exporter.to_csv(data, f"{filename}.csv")
    elif format == "excel":
        return exporter.to_excel(data, f"{filename}.xlsx")
    elif format == "jsonl":
        return exporter.to_jsonl(data, f"{filename}.jsonl")
    elif format == "graphml":
        return exporter.to_graphml(data, f"{filename}.graphml")
    elif format == "gexf":
        return exporter.to_gexf(data, f"{filename}.gexf")
    else:
        raise ValueError(f"Unknown format: {format}")
