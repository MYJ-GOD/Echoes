<template>
  <main class="family-detail-shell">
    <div class="family-detail-glow"></div>
    <div class="container family-detail-page">
      
      <button class="back-btn" @click="goBack">
        <span class="back-arrow">&lt;</span>
        {{ t("families.back") }}
      </button>

      
      <div v-if="loading" class="loading-state">
        <div class="loading-spinner"></div>
        <p>{{ t("families.loading") }}</p>
      </div>

      
      <div v-else-if="error" class="error-state">
        <div class="error-icon">!</div>
        <h3>{{ t("families.loadError") }}</h3>
        <p>{{ error }}</p>
        <button class="ghost-cta" @click="goBack">{{ t("families.backHome") }}</button>
      </div>

      <template v-else-if="family">
        
        <header class="detail-header">
          <div class="header-left">
            <div class="family-avatar">F</div>
            <div class="header-info">
              <h1 class="family-title">{{ family.name }}</h1>
              <div class="family-meta">
                <span class="member-count">
                  {{ t("families.memberCount", { count: members.length }) }}
                </span>
                <span class="create-time">{{ t("families.createdAt", { date: formatDate(family.createTime) }) }}</span>
              </div>
            </div>
          </div>
          <div class="header-actions" v-if="isOwner">
            <button class="primary-cta" @click="showAddMemberModal = true">
              {{ t("families.addMember") }}
            </button>
            <button class="ghost-cta" @click="goToSettings">
              {{ t("families.settings") }}
            </button>
          </div>
        </header>

        
        <section class="members-section card">
          <div class="section-header">
            <h3>{{ t("families.membersTitle") }}</h3>
            <span class="member-badge">{{ members.length }}</span>
          </div>

          <div v-if="membersLoading" class="mini-loading">
            <div class="mini-spinner"></div>
          </div>

          <div v-else-if="members.length === 0" class="empty-members">
            <p>{{ t("families.noMembers") }}</p>
          </div>

          <div v-else class="members-list">
            <div
              v-for="member in members"
              :key="member.id"
              class="member-item"
            >
              <div class="member-avatar" :class="getRoleClass(member.role)">
                {{ getMemberInitial(member.userName || "鐢ㄦ埛") }}
              </div>
              <div class="member-info">
                <div class="member-main">
                  <span class="member-name">{{ member.userName || t("families.unknown") }}</span>
                  <span class="role-badge" :class="`role-${member.role.toLowerCase()}`">
                    {{ getRoleText(member.role) }}
                  </span>
                </div>
                <span class="join-time">{{ t("families.joinedAt", { date: formatDate(member.createTime) }) }}</span>
              </div>
              <div class="member-actions" v-if="isOwner && !isSelf(member)">
                <button class="action-btn" @click="showRoleModal(member)">
                  {{ t("families.changeRole") }}
                </button>
                <button class="action-btn danger" @click="removeMember(member)">
                  {{ t("families.remove") }}
                </button>
              </div>
            </div>
          </div>
        </section>

        
        <div v-if="!isOwner" class="quit-section">
          <button class="quit-btn" @click="quitFamily">
            {{ t("families.quitFamily") }}
          </button>
        </div>
      </template>

      
      <div v-if="showAddMemberModal" class="modal-overlay" @click.self="showAddMemberModal = false">
        <div class="modal-content">
          <div class="modal-header">
            <h2>{{ t("families.addMember") }}</h2>
            <button class="modal-close" @click="showAddMemberModal = false">脳</button>
          </div>
          <div class="modal-body">
            <div class="search-section">
              <input
                type="text"
                v-model="searchKeyword"
                class="search-input"
                :placeholder="t('families.searchUserPlaceholder')"
                @input="searchUsers"
              />
            </div>
            <div v-if="searchResults.length > 0" class="search-results">
              <div
                v-for="user in searchResults"
                :key="user.userId"
                class="search-item"
                @click="selectUser(user)"
              >
                <div class="user-avatar">{{ getMemberInitial(user.name) }}</div>
                <div class="user-info">
                  <span class="user-name">{{ user.name }}</span>
                  <span class="user-phone">{{ user.phone }}</span>
                </div>
                <span class="add-icon">+</span>
              </div>
            </div>
            <div v-else-if="searchKeyword && !searching" class="search-empty">
              <p>{{ t("families.noSearchResults") }}</p>
            </div>
            <div v-if="selectedUser" class="selected-user-section">
              <div class="selected-user">
                <div class="user-avatar">{{ getMemberInitial(selectedUser.name) }}</div>
                <div class="user-info">
                  <span class="user-name">{{ selectedUser.name }}</span>
                </div>
                <button class="remove-btn" @click="selectedUser = null">脳</button>
              </div>
              <div class="role-select">
                <label>{{ t("families.selectRole") }}</label>
                <select v-model="selectedRole" class="role-dropdown">
                  <option value="PARENT">{{ t("families.roleParent") }}</option>
                  <option value="CHILD">{{ t("families.roleChild") }}</option>
                  <option value="CAREGIVER">{{ t("families.roleCaregiver") }}</option>
                  <option value="OTHER">{{ t("families.roleOther") }}</option>
                </select>
              </div>
            </div>
            <div class="modal-actions">
              <button class="cancel-btn" @click="showAddMemberModal = false">
                {{ t("families.cancel") }}
              </button>
              <button
                class="confirm-btn"
                :disabled="!selectedUser || adding"
                @click="addMember"
              >
                <span v-if="adding">{{ t("families.adding") }}</span>
                <span v-else>{{ t("families.confirmAdd") }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      
      <div v-if="showRoleModalFlag" class="modal-overlay" @click.self="showRoleModalFlag = false">
        <div class="modal-content small">
          <div class="modal-header">
            <h2>{{ t("families.changeRole") }}</h2>
            <button class="modal-close" @click="showRoleModalFlag = false">脳</button>
          </div>
          <div class="modal-body">
            <div class="role-options">
              <label
                v-for="role in roles"
                :key="role.value"
                class="role-option"
                :class="{ active: newRole === role.value }"
              >
                <input type="radio" v-model="newRole" :value="role.value" />
                <div class="role-content">
                  <span class="role-name">{{ role.label }}</span>
                  <span class="role-desc">{{ role.desc }}</span>
                </div>
              </label>
            </div>
            <div class="modal-actions">
              <button class="cancel-btn" @click="showRoleModalFlag = false">
                {{ t("families.cancel") }}
              </button>
              <button
                class="confirm-btn"
                :disabled="!newRole || updatingRole"
                @click="updateRole"
              >
                <span v-if="updatingRole">{{ t("families.saving") }}</span>
                <span v-else>{{ t("families.save") }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { getFamilyDetail, addFamilyMember, removeFamilyMember, updateMemberRole, type FamilyDetail, type FamilyMemberDetail, type FamilyRole } from "../../services/modules/family.api";
import { searchUsers as searchUsersApi } from "../../services/modules/family.api";
import { useUserStore } from "../../store/user";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

const familyId = computed(() => route.params.id as string);

const loading = ref(true);
const membersLoading = ref(true);
const error = ref<string | null>(null);
const family = ref<FamilyDetail | null>(null);
const members = ref<FamilyMemberDetail[]>([]);

const showAddMemberModal = ref(false);
const searchKeyword = ref("");
const searchResults = ref<{ userId: string; name: string; phone?: string }[]>([]);
const searching = ref(false);
const selectedUser = ref<{ userId: string; name: string } | null>(null);
const selectedRole = ref<FamilyRole>("CHILD");
const adding = ref(false);

const showRoleModalFlag = ref(false);
const editingMember = ref<FamilyMemberDetail | null>(null);
const newRole = ref<FamilyRole>("CHILD");
const updatingRole = ref(false);

const roles = [
  { value: "PARENT", label: t("families.roleParent"), desc: t("families.roleParentDesc") },
  { value: "CHILD", label: t("families.roleChild"), desc: t("families.roleChildDesc") },
  { value: "CAREGIVER", label: t("families.roleCaregiver"), desc: t("families.roleCaregiverDesc") },
  { value: "OTHER", label: t("families.roleOther"), desc: t("families.roleOtherDesc") },
];

const isOwner = computed(() => {
  return family.value?.ownerUserId === userStore.userId;
});

const isSelf = (member: FamilyMemberDetail): boolean => {
  return member.userId === userStore.userId;
};

const getMemberInitial = (name: string): string => {
  return name.charAt(0).toUpperCase();
};

const getRoleClass = (role: string): string => {
  return `role-${role.toLowerCase()}`;
};

const getRoleText = (role: string): string => {
  const map: Record<string, string> = {
    PARENT: t("families.roleParent"),
    CHILD: t("families.roleChild"),
    CAREGIVER: t("families.roleCaregiver"),
    OTHER: t("families.roleOther"),
  };
  return map[role] || role;
};

const formatDate = (date: string): string => {
  return new Date(date).toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
};

const goBack = () => {
  router.push("/families");
};

const goToSettings = () => {
  router.push(`/families/${familyId.value}/settings`);
};

const fetchFamily = async () => {
  try {
    loading.value = true;
    error.value = null;
    const result = await getFamilyDetail(familyId.value);
    if (result.code === 200 && result.data) {
      family.value = result.data;
      members.value = result.data.members || [];
    } else {
      error.value = result.message || t("families.loadError");
    }
  } catch (e) {
    error.value = t("families.loadError");
    console.error(e);
  } finally {
    loading.value = false;
    membersLoading.value = false;
  }
};

const searchUsers = async () => {
  if (!searchKeyword.value.trim()) {
    searchResults.value = [];
    return;
  }
  
  try {
    searching.value = true;
    const result = await searchUsersApi(searchKeyword.value);
    if (result.code === 200 && result.data) {
      const memberIds = members.value.map(m => m.userId);
      searchResults.value = result.data.filter(u => !memberIds.includes(u.userId));
    }
  } catch (e) {
    console.error("鎼滅储鐢ㄦ埛澶辫触:", e);
  } finally {
    searching.value = false;
  }
};

const selectUser = (user: { userId: string; name: string; phone?: string }) => {
  selectedUser.value = { userId: user.userId, name: user.name };
  searchKeyword.value = "";
  searchResults.value = [];
};

const addMember = async () => {
  if (!selectedUser.value) return;
  
  try {
    adding.value = true;
    const result = await addFamilyMember(familyId.value, {
      userId: selectedUser.value.userId,
      role: selectedRole.value,
    });
    if (result.code === 200) {
      showAddMemberModal.value = false;
      selectedUser.value = null;
      selectedRole.value = "CHILD";
      await fetchFamily();
    } else {
      alert(result.message || t("families.addMemberFailed"));
    }
  } catch (e) {
    console.error("娣诲姞鎴愬憳澶辫触:", e);
    alert(t("families.addMemberFailed"));
  } finally {
    adding.value = false;
  }
};

const showRoleModal = (member: FamilyMemberDetail) => {
  editingMember.value = member;
  newRole.value = member.role as FamilyRole;
  showRoleModalFlag.value = true;
};

const updateRole = async () => {
  if (!editingMember.value || !newRole.value) return;
  
  try {
    updatingRole.value = true;
    const result = await updateMemberRole(familyId.value, editingMember.value.userId, newRole.value);
    if (result.code === 200) {
      showRoleModalFlag.value = false;
      editingMember.value = null;
      await fetchFamily();
    } else {
      alert(result.message || t("families.updateRoleFailed"));
    }
  } catch (e) {
    console.error("鏇存柊瑙掕壊澶辫触:", e);
    alert(t("families.updateRoleFailed"));
  } finally {
    updatingRole.value = false;
  }
};

const removeMember = async (member: FamilyMemberDetail) => {
  if (!confirm(t("families.confirmRemove", { name: member.userName || t("families.unknown") }))) return;
  
  try {
    const result = await removeFamilyMember(familyId.value, member.userId);
    if (result.code === 200) {
      await fetchFamily();
    } else {
      alert(result.message || t("families.removeMemberFailed"));
    }
  } catch (e) {
    console.error("绉婚櫎鎴愬憳澶辫触:", e);
    alert(t("families.removeMemberFailed"));
  }
};

const quitFamily = async () => {
  if (!confirm(t("families.confirmQuit"))) return;
  
  try {
    const result = await removeFamilyMember(familyId.value, userStore.userId);
    if (result.code === 200) {
      router.push("/families");
    } else {
      alert(result.message || t("families.quitFailed"));
    }
  } catch (e) {
    console.error("閫€鍑哄搴け璐?", e);
    alert(t("families.quitFailed"));
  }
};

onMounted(() => {
  fetchFamily();
});
</script>

<style scoped>
.family-detail-shell {
  position: relative;
  padding: var(--space-6) 0 var(--space-9);
  overflow: hidden;
}

.family-detail-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(720px 480px at 50% 0%, rgba(96, 165, 250, 0.1), transparent 60%);
  pointer-events: none;
}

.family-detail-page {
  position: relative;
  z-index: 1;
  max-width: 800px;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px 0;
  border: none;
  background: transparent;
  color: var(--color-muted);
  font-size: 14px;
  cursor: pointer;
  transition: color 0.2s ease;
  margin-bottom: var(--space-5);
}

.back-btn:hover {
  color: var(--color-text);
}

.back-arrow {
  font-size: 18px;
}

/* 鍔犺浇/閿欒鐘舵€?*/
.loading-state,
.error-state {
  display: grid;
  gap: var(--space-4);
  justify-items: center;
  padding: var(--space-9) 0;
  text-align: center;
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 3px solid rgba(96, 165, 250, 0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon {
  font-size: 48px;
}

.ghost-cta {
  padding: 10px 18px;
  border-radius: 999px;
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: var(--color-text);
  background: rgba(255, 255, 255, 0.8);
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ghost-cta:hover {
  border-color: rgba(59, 130, 246, 0.6);
  background: rgba(96, 165, 250, 0.1);
}

/* 鍗＄墖鏍峰紡 */
.card {
  padding: var(--space-5);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(96, 165, 250, 0.2);
  box-shadow: var(--shadow-card);
  margin-bottom: var(--space-4);
}

/* 澶撮儴淇℃伅 */
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-5);
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
}

.header-left {
  display: flex;
  gap: var(--space-4);
}

.family-avatar {
  width: 72px;
  height: 72px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(96, 165, 250, 0.3), rgba(59, 130, 246, 0.2));
  display: grid;
  place-items: center;
  font-size: 32px;
  flex-shrink: 0;
}

.header-info {
  display: grid;
  gap: var(--space-2);
}

.family-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 24px;
}

.family-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.member-count {
  font-size: 14px;
  color: var(--color-muted);
}

.create-time {
  font-size: 13px;
  color: var(--color-muted);
}

.header-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.primary-cta {
  padding: 10px 18px;
  border-radius: 999px;
  border: none;
  font-weight: 600;
  font-size: 14px;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  color: white;
  box-shadow: 0 12px 25px rgba(59, 130, 246, 0.28);
  cursor: pointer;
  transition: all 0.2s ease;
}

.primary-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 30px rgba(59, 130, 246, 0.35);
}

/* 鎴愬憳鍒楄〃 */
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.section-header h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 18px;
}

.member-badge {
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(96, 165, 250, 0.2);
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 600;
}

.mini-loading {
  display: grid;
  justify-items: center;
  padding: var(--space-4) 0;
}

.mini-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(96, 165, 250, 0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.empty-members {
  text-align: center;
  padding: var(--space-4) 0;
  color: var(--color-muted);
}

.members-list {
  display: grid;
  gap: var(--space-3);
}

.member-item {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  border-radius: 14px;
  background: rgba(96, 165, 250, 0.08);
}

.member-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(96, 165, 250, 0.3), rgba(59, 130, 246, 0.2));
  display: grid;
  place-items: center;
  font-weight: 600;
  color: #1e40af;
  flex-shrink: 0;
}

.member-avatar.role-parent {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.3), rgba(245, 158, 11, 0.2));
  color: #92400e;
}

.member-avatar.role-child {
  background: linear-gradient(135deg, rgba(96, 165, 250, 0.3), rgba(59, 130, 246, 0.2));
  color: #1e40af;
}

.member-avatar.role-caregiver {
  background: linear-gradient(135deg, rgba(74, 222, 128, 0.3), rgba(34, 197, 94, 0.2));
  color: #166534;
}

.member-info {
  flex: 1;
  display: grid;
  gap: 2px;
}

.member-main {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.member-name {
  font-weight: 500;
  font-size: 15px;
}

.role-badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.role-badge.role-parent {
  background: rgba(251, 191, 36, 0.2);
  color: #b45309;
}

.role-badge.role-child {
  background: rgba(96, 165, 250, 0.2);
  color: #1d4ed8;
}

.role-badge.role-caregiver {
  background: rgba(74, 222, 128, 0.2);
  color: #166534;
}

.role-badge.role-other {
  background: rgba(156, 163, 175, 0.2);
  color: #4b5563;
}

.join-time {
  font-size: 12px;
  color: var(--color-muted);
}

.member-actions {
  display: flex;
  gap: var(--space-2);
}

.action-btn {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid rgba(96, 165, 250, 0.25);
  background: rgba(255, 255, 255, 0.9);
  color: var(--color-text);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background: rgba(96, 165, 250, 0.1);
}

.action-btn.danger {
  border-color: rgba(248, 113, 113, 0.4);
  color: #b91c1c;
}

.action-btn.danger:hover {
  background: rgba(248, 113, 113, 0.1);
}

/* 閫€鍑哄搴?*/
.quit-section {
  margin-top: var(--space-6);
  padding-top: var(--space-6);
  border-top: 1px solid rgba(239, 227, 215, 0.6);
  text-align: center;
}

.quit-btn {
  padding: 12px 24px;
  border-radius: 12px;
  border: 1px solid rgba(248, 113, 113, 0.4);
  background: rgba(248, 113, 113, 0.1);
  color: #b91c1c;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.quit-btn:hover {
  background: rgba(248, 113, 113, 0.2);
}

/* 寮圭獥 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: grid;
  place-items: center;
  z-index: 100;
  padding: var(--space-4);
}

.modal-content {
  width: 100%;
  max-width: 480px;
  background: white;
  border-radius: 20px;
  overflow: hidden;
}

.modal-content.small {
  max-width: 400px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-5);
  border-bottom: 1px solid rgba(239, 227, 215, 0.9);
}

.modal-header h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 20px;
}

.modal-close {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(96, 165, 250, 0.2);
  border-radius: 50%;
  font-size: 20px;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all 0.2s ease;
}

.modal-close:hover {
  background: rgba(96, 165, 250, 0.4);
}

.modal-body {
  padding: var(--space-5);
  max-height: 60vh;
  overflow-y: auto;
}

.search-section {
  margin-bottom: var(--space-4);
}

.search-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid rgba(229, 139, 58, 0.3);
  border-radius: 12px;
  font-size: 15px;
  outline: none;
  transition: all 0.2s ease;
}

.search-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.search-results,
.selected-user-section {
  display: grid;
  gap: var(--space-2);
}

.search-item,
.selected-user {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: 12px;
  background: rgba(96, 165, 250, 0.08);
  cursor: pointer;
  transition: all 0.2s ease;
}

.search-item:hover {
  background: rgba(96, 165, 250, 0.15);
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(96, 165, 250, 0.3), rgba(59, 130, 246, 0.2));
  display: grid;
  place-items: center;
  font-weight: 600;
  color: #1e40af;
  flex-shrink: 0;
}

.user-info {
  flex: 1;
  display: grid;
  gap: 2px;
}

.user-name {
  font-weight: 500;
  font-size: 14px;
}

.user-phone {
  font-size: 12px;
  color: var(--color-muted);
}

.add-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
  display: grid;
  place-items: center;
  font-size: 18px;
  font-weight: bold;
}

.remove-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: rgba(248, 113, 113, 0.2);
  border-radius: 50%;
  color: #b91c1c;
  font-size: 16px;
  cursor: pointer;
  display: grid;
  place-items: center;
}

.role-select {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  background: rgba(255, 255, 255, 0.9);
  border-radius: 12px;
}

.role-select label {
  font-size: 13px;
  color: var(--color-muted);
}

.role-dropdown {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid rgba(229, 139, 58, 0.3);
  border-radius: 10px;
  font-size: 14px;
  outline: none;
  cursor: pointer;
}

.search-empty {
  text-align: center;
  padding: var(--space-4);
  color: var(--color-muted);
}

.modal-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid rgba(239, 227, 215, 0.6);
}

.cancel-btn,
.confirm-btn {
  flex: 1;
  padding: 12px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cancel-btn {
  border: 1px solid rgba(229, 139, 58, 0.3);
  background: rgba(255, 255, 255, 0.9);
  color: var(--color-text);
}

.confirm-btn {
  border: none;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  color: white;
}

.confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 瑙掕壊閫夐」 */
.role-options {
  display: grid;
  gap: var(--space-3);
}

.role-option {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: 14px;
  border: 1px solid rgba(239, 227, 215, 0.6);
  background: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  transition: all 0.2s ease;
}

.role-option:hover {
  border-color: rgba(96, 165, 250, 0.4);
}

.role-option.active {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.08);
}

.role-option input {
  margin-top: 4px;
}

.role-content {
  display: grid;
  gap: 2px;
}

.role-name {
  font-weight: 500;
  font-size: 14px;
}

.role-desc {
  font-size: 12px;
  color: var(--color-muted);
}
</style>


