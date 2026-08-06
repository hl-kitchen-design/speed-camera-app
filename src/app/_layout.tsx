import { Stack } from 'expo-router';

export default function RootLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(map)/index" />
      <Stack.Screen name="settings" options={{ headerShown: true, title: '設定' }} />
    </Stack>
  );
}
