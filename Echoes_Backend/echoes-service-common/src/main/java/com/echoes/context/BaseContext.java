package com.echoes.context;

public class BaseContext {

    public static ThreadLocal<java.util.UUID> threadLocal = new ThreadLocal<>();

    public static void setCurrentId(java.util.UUID id) {
        threadLocal.set(id);
    }

    public static java.util.UUID getCurrentId() {
        return threadLocal.get();
    }

    public static void removeCurrentId() {
        threadLocal.remove();
    }

}
