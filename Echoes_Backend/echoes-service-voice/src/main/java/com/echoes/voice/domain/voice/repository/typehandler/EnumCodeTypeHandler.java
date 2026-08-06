package com.echoes.voice.domain.voice.repository.typehandler;

import org.apache.ibatis.type.BaseTypeHandler;
import org.apache.ibatis.type.JdbcType;
import org.apache.ibatis.type.MappedJdbcTypes;
import org.apache.ibatis.type.MappedTypes;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.sql.CallableStatement;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

@MappedJdbcTypes({JdbcType.VARCHAR, JdbcType.CHAR, JdbcType.INTEGER})
@MappedTypes({})
public class EnumCodeTypeHandler<E extends Enum<E>> extends BaseTypeHandler<E> {

    private final Class<E> type;
    private final Method getCodeMethod;
    private final Field codeField;
    private final boolean isStringCode;
    private final boolean useEnumNameFallback;

    @SuppressWarnings("unchecked")
    public EnumCodeTypeHandler(Class<?> type) {
        if (type == null) {
            throw new IllegalArgumentException("Type argument cannot be null");
        }
        if (!type.isEnum()) {
            throw new IllegalArgumentException("Type " + type.getName() + " must be an enum");
        }
        this.type = (Class<E>) type;

        Method codeMethod = null;
        Field field = null;
        boolean stringCode = false;
        boolean enumNameFallback = false;

        try {
            try {
                codeMethod = type.getDeclaredMethod("getCode");
                codeMethod.setAccessible(true);
                Class<?> returnType = codeMethod.getReturnType();
                stringCode = String.class.equals(returnType);
            } catch (NoSuchMethodException e) {
                try {
                    field = type.getDeclaredField("code");
                    field.setAccessible(true);
                    stringCode = String.class.equals(field.getType());
                } catch (NoSuchFieldException noSuchFieldException) {
                    // Fallback for enums without code/getCode: persist enum name.
                    enumNameFallback = true;
                    stringCode = true;
                }
            }
        } catch (Exception e) {
            throw new IllegalArgumentException("Failed to initialize EnumCodeTypeHandler: " + e.getMessage(), e);
        }

        this.getCodeMethod = codeMethod;
        this.codeField = field;
        this.isStringCode = stringCode;
        this.useEnumNameFallback = enumNameFallback;
    }

    @Override
    public void setNonNullParameter(PreparedStatement ps, int i, E parameter, JdbcType jdbcType) throws SQLException {
        Object code = getCode(parameter);
        if (isStringCode) {
            ps.setString(i, (String) code);
        } else {
            ps.setInt(i, (Integer) code);
        }
    }

    @Override
    public E getNullableResult(ResultSet rs, String columnName) throws SQLException {
        Object code = isStringCode ? rs.getString(columnName) : rs.getInt(columnName);
        return code == null ? null : getEnumByCode(code);
    }

    @Override
    public E getNullableResult(ResultSet rs, int columnIndex) throws SQLException {
        Object code = isStringCode ? rs.getString(columnIndex) : rs.getInt(columnIndex);
        return code == null ? null : getEnumByCode(code);
    }

    @Override
    public E getNullableResult(CallableStatement cs, int columnIndex) throws SQLException {
        Object code = isStringCode ? cs.getString(columnIndex) : cs.getInt(columnIndex);
        return code == null ? null : getEnumByCode(code);
    }

    private Object getCode(E enumValue) {
        try {
            if (useEnumNameFallback) {
                return enumValue.name();
            }
            if (getCodeMethod != null) {
                return getCodeMethod.invoke(enumValue);
            }
            if (codeField != null) {
                return codeField.get(enumValue);
            }
            throw new IllegalStateException("Enum has no code accessor");
        } catch (Exception e) {
            throw new RuntimeException("Failed to read enum code: " + e.getMessage(), e);
        }
    }

    private E getEnumByCode(Object code) {
        if (code == null) {
            return null;
        }
        E[] enumConstants = type.getEnumConstants();
        if (enumConstants == null) {
            return null;
        }
        String codeStr = String.valueOf(code);
        for (E enumConstant : enumConstants) {
            Object enumCode = getCode(enumConstant);
            if (enumCode == null) {
                continue;
            }
            String enumCodeStr = String.valueOf(enumCode);
            // 兼容大小写不敏感匹配
            if (codeStr.equalsIgnoreCase(enumCodeStr)) {
                return enumConstant;
            }
        }
        // 尝试使用枚举名称直接匹配（兼容数据库中的大写值）
        for (E enumConstant : enumConstants) {
            if (enumConstant.name().equalsIgnoreCase(codeStr)) {
                return enumConstant;
            }
        }
        throw new IllegalArgumentException("Unknown enum code: " + code);
    }
}
