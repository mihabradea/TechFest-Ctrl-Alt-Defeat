import React, { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { Redirect } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";


export default function Index() {
  // const [token, setToken] = useState<string | null | undefined>(undefined);

  // useEffect(() => {
  //   (async () => {
  //     try {
  //       const t = await AsyncStorage.getItem("token");
  //       setToken(t); // null if not found
  //     } catch {
  //       setToken(null);
  //     }
  //   })();
  // }, []);

  // if (token === undefined) {
  //   return (
  //     <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
  //       <ActivityIndicator />
  //     </View>
  //   );
  // }

  // return token ? <Redirect href="/" /> : <Redirect href="/login" />;
  return <Redirect href="/login" />


  // return <Redirect href="/chat" />
}
