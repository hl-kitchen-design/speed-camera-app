import { View, Text, StyleSheet, ScrollView } from 'react-native';

export default function SettingsScreen() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.disclaimerTitle}>免責聲明</Text>
      <Text style={styles.disclaimerBody}>
        本 App 資訊來源為政府開放資料與各縣市警局公告，僅供參考，實際執法標準與地點以官方公告為準，請遵守道路交通安全規則。
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F2F2F7' },
  content: { padding: 20 },
  disclaimerTitle: { fontSize: 18, fontWeight: '600', marginBottom: 8 },
  disclaimerBody: { fontSize: 14, color: '#3C3C43', lineHeight: 20 },
});
